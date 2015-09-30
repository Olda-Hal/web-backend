import json, falcon, os, magic, multipart
from sqlalchemy import func

from db import session
from model import ModuleType
import model

def _module_to_json(module):
	return { 'id': module.id, 'type': module.type, 'name': module.name, 'description': module.description }

def _load_questions(module_id):
	return session.query(model.QuizQuestion).filter(model.QuizQuestion.module == module_id).order_by(model.QuizQuestion.order).all()

def _load_sortable(module_id):
	fixed = session.query(model.Sortable).filter(model.Sortable.module == module_id, model.Sortable.type == 'fixed').order_by(model.Sortable.order).all()
	movable = session.query(model.Sortable).filter(model.Sortable.module == module_id, model.Sortable.type == 'movable').order_by(model.Sortable.order).all()

	return (fixed, movable)

class Module(object):

	def on_get(self, req, resp, id):
		user = req.context['user']

		if not user.is_logged_in():
			resp.status = falcon.HTTP_400
			return

		module = session.query(model.Module).get(id)
		module_json = _module_to_json(module)
		count = session.query(model.Evaluation.points).filter(model.Evaluation.user == user.id, model.Evaluation.module == id).count()

		if count > 0:
			status = session.query(func.max(model.Evaluation.points).label('points')).\
				filter(model.Evaluation.user == user.id, model.Evaluation.module == id).first()
			module_json['state'] = 'correct' if status.points == module.max_points else 'incorrect'
		else:
			module_json['state'] = 'blank'

		if module.type == ModuleType.PROGRAMMING:
			code = self._build_programming(module.id)
			module_json['code'] = code
			module_json['default_code'] = code
		elif module.type == ModuleType.QUIZ:
			module_json['questions'] = self._build_quiz(module.id)
		elif module.type == ModuleType.SORTABLE:
			module_json['sortable_list'] = self._build_sortable(module.id)
		elif module.type == ModuleType.GENERAL:
			module_json['state'] = 'correct' if count > 0 else 'blank'

		req.context['result'] = { 'module': module_json }

	def _build_programming(self, module_id):
		programming = session.query(model.Programming).filter(model.Programming.module == module_id).first()

		return programming.default_code

	def _quiz_question_to_json(self, question):
		return {
			'type': question.type,
			'question': question.question,
			'options': [ option.value for option in question.options ]
		}

	def _build_quiz(self, module_id):
		questions = _load_questions(module_id)

		return [ self._quiz_question_to_json(question) for question in questions ]

	def _sortable_type_to_json(self, sortable_type):
		return [ { 'content': row.content, 'style': row.style } for row in sortable_type ]

	def _build_sortable(self, module_id):
		fixed, movable = _load_sortable(module_id)

		return { 'fixed': self._sortable_type_to_json(fixed), 'movable': self._sortable_type_to_json(movable) }

def quiz_evaluate(task, module, data):
	report = '=== Evaluating quiz id \'%s\' for task id \'%s\' ===\n\n' % (module, task)
	report += ' Raw data: ' + json.dumps(data) + '\n'
	report += ' Evaluation:\n'

	overall_results = True
	questions = _load_questions(module)
	i = 0

	for question in questions:
		answers_user = [ int(item) for item in data[i] ]
		answers_correct = []

		j = 0
		for option in question.options:
			if option.is_correct:
				answers_correct.append(j)
			j += 1

		is_correct = (answers_user == answers_correct)

		report += '  [%s] Question %d (id: %d) -- user answers: %s, correct answers: %s\n' % ('y' if is_correct else 'n', i, question.id, answers_user, answers_correct)
		overall_results &= is_correct
		i += 1

	report += '\n Overall result: [' + ('y' if overall_results else 'n') + ']'

	return (overall_results, report)

def sortable_evaluate(task, module, data):
	report = '=== Evaluating sortable id \'%s\' for task id \'%s\' ===\n\n' % (module, task)
	report += ' Raw data: ' + json.dumps(data) + '\n'
	report += ' Evaluation:\n'

	sortable = session.query(model.Sortable).filter(model.Sortable.module == module).order_by(model.Sortable.order).all()
	correct_order = {}
	user_order = { i: data[i].encode('utf-8') for i in range(len(data)) }

	i = 0
	j = 0
	for item in sortable:
		if item.type == 'fixed':
			value = 'a' + str(i)
			i += 1
		else:
			value = 'b' + str(j)
			j += 1

		correct_order[item.correct_position - 1] = value

	result = (correct_order == user_order)

	report += '  User order: %s\n' % user_order
	report += '  Correct order: %s\n' % correct_order
	report += '\n Overall result: [%s]' % ('y' if result else 'n')

	return (result, report)

class ModuleSubmit(object):

	def _upload_files(self, req, module, user_id, resp):
		report = '=== Uploading files for module id \'%s\' for task id \'%s\' ===\n\n' % (module.id, module.task)

		evaluation = model.Evaluation(user=user_id, module=module.id)
		session.add(evaluation)
		session.commit()

		dir = 'submissions/module_%d/user_%d' % (module.id, user_id)

		try:
			os.makedirs(dir)
		except OSError:
			pass

		if not os.path.isdir(dir):
			resp.status = falcon.HTTP_400
			req.context['result'] = { 'result': 'incorrect' }
			return

		files = multipart.MultiDict()
		content_type, options = multipart.parse_options_header(req.content_type)
		boundary = options.get('boundary','')

		if not boundary:
			raise multipart.MultipartError("No boundary for multipart/form-data.")

		for part in multipart.MultipartParser(req.stream, boundary, req.content_length):
			path = '%s/%d_%s' % (dir, evaluation.id, part.filename)
			part.save_as(path)
			mime = magic.Magic(mime=True).from_file(path)

			report += '  [y] uploaded file: \'%s\' (mime: %s) to file %s\n' % (part.filename, mime, path)
			submitted_file = model.SubmittedFile(evaluation=evaluation.id, mime=mime, path=path)

			session.add(submitted_file)

		evaluation.report = report
		session.add(evaluation)
		session.commit()
		session.close()

		req.context['result'] = { 'result': 'correct' }

	def _evaluate_code(self, req, module, user_id, resp, data):
		evaluation = model.Evaluation(user=user_id, module=module.id)
		session.add(evaluation)
		session.commit()

		code = model.SubmittedCode(evaluation=evaluation.id, code=data)
		session.add(code)

		if not module.autocorrect:
			session.commit()
			session.close()
			return

	def on_post(self, req, resp, id):
		user = req.context['user']

		if not user.is_logged_in():
			resp.status = falcon.HTTP_400
			return

		module = session.query(model.Module).get(id)

		if module.type == ModuleType.GENERAL:
			self._upload_files(req, module, user.id, resp)
			return

		data = json.loads(req.stream.read())['content']

		if module.type == ModuleType.PROGRAMMING:
			self._evaluate_code(req, module, user.id, resp, data)
			return

		if module.type == ModuleType.QUIZ:
			result, report = quiz_evaluate(module.task, module.id, data)
		elif module.type == ModuleType.SORTABLE:
			result, report = sortable_evaluate(module.task, module.id, data)

		evaluation = model.Evaluation(user=user.id, module=module.id, points=(module.max_points if result else 0), full_report=report)
		req.context['result'] = { 'result': 'correct' if result else 'incorrect' }

		session.add(evaluation)
		session.commit()
		session.close()
