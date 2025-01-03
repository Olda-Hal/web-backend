import falcon
import json
from sqlalchemy.exc import SQLAlchemyError
import dateutil.parser

from db import session
import model
import util
import datetime


class Wave(object):

    def on_get(self, req, resp, id):
        try:
            user = req.context['user']
            wave = session.query(model.Wave).get(id)

            if wave is None:
                resp.status = falcon.HTTP_404
                return

            req.context['result'] = {'wave': util.wave.to_json(wave)}

        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

    # UPDATE vlny
    def on_put(self, req, resp, id):
        try:
            user = req.context['user']

            if (not user.is_logged_in()) or (not user.is_org()):
                resp.status = falcon.HTTP_400
                return

            data = json.loads(req.stream.read().decode('utf-8'))['wave']

            wave = session.query(model.Wave).get(id)
            if wave is None:
                resp.status = falcon.HTTP_404
                return

            # Menit vlnu muze jen ADMIN nebo aktualni GARANT vlny.
            if not user.is_admin() and user.id != wave.garant:
                resp.status = falcon.HTTP_400
                return

            wave.index = data['index']
            wave.caption = data['caption']
            if data['time_published']:
                wave.time_published = dateutil.parser.parse(data['time_published'])
            wave.garant = data['garant']

            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

        self.on_get(req, resp, id)

    # Smazani vlny
    def on_delete(self, req, resp, id):
        try:
            user = req.context['user']

            # Vlnu mohou smazat jen admini
            if (not user.is_logged_in()) or (not user.is_admin()):
                resp.status = falcon.HTTP_400
                return

            wave = session.query(model.Wave).get(id)
            if wave is None:
                resp.status = falcon.HTTP_404
                return

            # Smazat lze jen neprazdnou vlnu.
            tasks_cnt = session.query(model.Task).\
                filter(model.Task.wave == wave.id).\
                count()

            if tasks_cnt > 0:
                resp.status = falcon.HTTP_403
                return

            session.delete(wave)
            session.commit()
            req.context['result'] = {}

        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()


class Waves(object):

    def on_get(self, req, resp):
        try:
            user = req.context['user']
            can_see_unrealesed = user.is_logged_in() and (user.is_org() or user.is_tester())
            waves = session.query(model.Wave).\
                filter(model.Wave.year == req.context['year']).all()

            max_points = util.task.max_points_wave_dict()

            req.context['result'] = {
                'waves': [
                    util.wave.to_json(wave, max_points[wave.id])
                    for wave in waves if (can_see_unrealesed or wave.time_published < datetime.datetime.now())
                ]
            }

        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

    # Vytvoreni nove vlny
    def on_post(self, req, resp):
        try:
            user = req.context['user']
            year = req.context['year']

            # Vytvorit novou vlnu mohou jen admini.
            if (not user.is_logged_in()) or (not user.is_admin()):
                resp.status = falcon.HTTP_400
                return

            data = json.loads(req.stream.read().decode('utf-8'))['wave']

            wave = model.Wave(
                year=year,
                index=data['index'],
                caption=data['caption'],
                garant=data['garant'],
                time_published=dateutil.parser.parse(data['time_published'])
            )

            session.add(wave)
            session.commit()
            req.context['result'] = {'wave': util.wave.to_json(wave)}
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()
