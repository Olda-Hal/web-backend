import json
from sqlalchemy import func, or_, distinct

from db import session
import model

from util import PrerequisitiesEvaluator, decode_form_data
import endpoint.module
import util.task
import util.prerequisite


def _task_to_json(task, points=None, user_id=None, currently_active=None):
	try:
		max_score = points[task.id] if points else task.util.max_points(task.id)
	except KeyError:
		max_score = 0

	if not currently_active:
		currently_active = util.task.currently_active(user_id)

	is_active = True if task.id in currently_active else PrerequisitiesEvaluator(task.prerequisite_obj, currently_active).evaluate()

	return {
		'id': task.id,
		'title': task.title,
		'author': task.author,
		'category': task.category,
		'intro': task.intro,
		'body': task.body,
		'max_score': max_score,
		'position': [ task.position_x, task.position_y ],
		'thread': task.thread,
		'time_published': task.time_published.isoformat(),
		'time_deadline': task.time_deadline.isoformat(),
		'active': is_active,
		'modules': [ module.id for module in task.modules ],
		'best_scores': [ 1 ],
		'my_score': task.util.points(task.id, user_id) if user_id is not None else None,
		'solution': 'Prehledne vysvetlene reseni prikladu. Cely priklad spocival v blabla',
		'submissions': [],
		'prerequisities': [] if not task.prerequisite_obj else util.prerequisite.to_json(task.prerequisite_obj),
		'picture_base': task.picture_base,
		'picture_suffix': '.svg'
	}

class Task(object):

	def on_get(self, req, resp, id):
		task = session.query(model.Task).get(id)

		req.context['result'] = { 'task': _task_to_json(task) }


class Tasks(object):

	def on_get(self, req, resp):
		tasks = session.query(model.Task).all()
		points_dict = util.task.max_points_dict()

		currently_active = util.task.currently_active(14)

		req.context['result'] = { 'tasks': [ _task_to_json(task, points=points_dict, currently_active=currently_active) for task in tasks ] }
