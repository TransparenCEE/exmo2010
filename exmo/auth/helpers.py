# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011, 2013 Al Nikolov
# Copyright 2010, 2011 non-profit partnership Institute of Information Freedom Development
# Copyright 2012, 2013 Foundation "Institute for Information Freedom Development"
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
 Помощники для бекенда. По помощнику на каждый класс модели.
"""

from exmo2010.models import Task, MONITORING_INTERACTION, MONITORING_FINALIZING, MONITORING_PUBLISHED


def monitoring_permission(user, priv, monitoring):
    #определяет показывать ссылку на рейтинг или на задачи
    if priv == 'exmo2010.view_tasks':
        if monitoring.is_published:
            if user.is_active and user.profile.is_expert:
                return True
        else:
            return True

    if priv in ('exmo2010.admin_monitoring',
                'exmo2010.create_monitoring',
                'exmo2010.edit_monitoring'):
        if user.is_active:
            if user.profile.is_manager_expertB:
                return True

    if priv == 'exmo2010.delete_monitoring':
        if user.is_active:
            if user.profile.is_manager_expertB and not monitoring.is_published:
                return True

    if priv in ('exmo2010.view_monitoring', 'exmo2010.rating_monitoring'):
        if user.is_active:
            if user.profile.is_expertA or user.profile.is_manager_expertB:
                return True
        # monitoring have one approved task for anonymous and publish and not hidden
        if Task.approved_tasks.filter(organization__monitoring=monitoring).exists() \
                and monitoring.is_published \
                and not monitoring.hidden:
            return True
        if user.is_active:  # minimaze query
            profile = user.profile
            if profile.is_expert \
                    and Task.objects.filter(organization__monitoring=monitoring, user=user).exists() \
                    and monitoring.is_active:
                return True
            elif profile.is_organization \
                and Task.approved_tasks.filter(
                    organization__monitoring=monitoring,
                    organization__monitoring__status__in=(
                        MONITORING_INTERACTION,
                        MONITORING_FINALIZING,
                        MONITORING_PUBLISHED,
                    ),
                    organization__in=profile.organization.all()).exists():
                return True

    return False


def task_permission(user, priv, task):
    if user.is_active:
        if user.profile.is_expertA or user.profile.is_manager_expertB:
            return True
    if priv == 'exmo2010.view_task':
        if task.approved and task.organization.monitoring.is_published:
            return True
        if user.is_active:
            profile = user.profile
            if profile.is_expert and task.user == user: return True
            if profile.is_expert:
                return user.has_perm('exmo2010.fill_task', task)
            elif profile.is_organization or profile.is_customer:
                if task.organization in profile.organization.all() \
                    and task.approved \
                    and user.has_perm('exmo2010.view_monitoring',
                                      task.organization.monitoring):
                    return True
        elif task.approved and user.has_perm('exmo2010.view_monitoring',
                                             task.organization.monitoring):
            return True  # anonymous user
    elif priv == 'exmo2010.close_task':
        if task.open and task.user == user \
            and task.organization.monitoring.is_rate:
            return True
    elif priv == 'exmo2010.open_task':
        if task.ready and task.user == user \
            and task.organization.monitoring.is_rate:
            return True
    elif priv == 'exmo2010.fill_task':  # create_score
        if task.open and task.user == user and \
                task.organization.monitoring.is_rate:
            return True
        if task.user == user and (task.organization.monitoring.is_interact or
                                      task.organization.monitoring.is_finishing):
            return True

    elif priv == 'exmo2010.add_comment_score':
        if user.is_active:
            profile = user.profile
            if profile.is_expertA and \
                    (task.organization.monitoring.is_interact or
                         task.organization.monitoring.is_finishing):
                return True

            if profile.is_expertB and task.user == user and \
                    (task.organization.monitoring.is_interact or
                         task.organization.monitoring.is_finishing):
                return True

            if profile.is_organization and \
                    user.has_perm('exmo2010.view_task', task) and \
                            task.organization in profile.organization.all() and \
                    task.organization.monitoring.is_interact:
                return True
    return False


def score_permission(user, priv, score):
    task = score.task
    monitoring = task.organization.monitoring

    if user.is_authenticated():
        profile = user.profile

    if priv == 'exmo2010.view_score':
        if score.task.organization not in score.parameter.exclude.all():
            return user.has_perm('exmo2010.view_task', score.task)

    if priv == 'exmo2010.edit_score':
        if score.task.organization not in score.parameter.exclude.all():
            return user.has_perm('exmo2010.fill_task', score.task)

    if priv == 'exmo2010.delete_score':
        return user.has_perm('exmo2010.fill_task', score.task)

    if priv == 'exmo2010.add_comment_score':
        if user.is_active:
            if (profile.is_expertB and not profile.is_expertA) and (monitoring.is_interact or monitoring.is_finishing):
                return True
            if profile.is_expertA and (monitoring.is_interact or monitoring.is_finishing or monitoring.is_published):
                return True
            if profile.is_organization and monitoring.is_interact:
                return True

    if priv == 'exmo2010.view_comment_score':
        if user.is_active and (monitoring.is_interact or monitoring.is_finishing or monitoring.is_published):
            if profile.is_expertA:
                return True
            if profile.is_expertB and task.user_id == user.id:
                return True
            if profile.is_organization and task.organization in profile.organization.all():
                return True

    if priv == 'exmo2010.close_comment_score':
        if user.is_active:
            if profile.is_expertA and (monitoring.is_interact or monitoring.is_finishing or monitoring.is_published):
                return True

    if priv == 'exmo2010.view_claim_score':
        if user.is_active and not monitoring.is_prepare:
            if profile.is_expertA:
                return True
            if profile.is_expertB and task.user_id == user.id:
                return True

    if priv == 'exmo2010.add_claim_score':
        if user.is_active:
            if profile.is_expertA and not (monitoring.is_prepare or monitoring.is_published):
                return True

    if priv == 'exmo2010.answer_claim_score':
        if user.is_active:
            if (profile.is_expertB and not profile.is_expertA) and not (monitoring.is_prepare or monitoring.is_published):
                return True

    if priv == 'exmo2010.delete_claim_score':
        if user.is_active:
            if profile.is_expertA:
                return True

    if priv == 'exmo2010.view_claim':
        if user.is_active:
            if profile.is_expert and not monitoring.is_prepare:
                return True

    if priv == 'exmo2010.view_clarification_score':
        if user.is_active and not monitoring.is_prepare:
            if profile.is_expertA:
                return True
            if profile.is_expertB and task.user_id == user.id:
                return True

    if priv == 'exmo2010.add_clarification_score':
        if user.is_active:
            if profile.is_expertA and not (monitoring.is_prepare or monitoring.is_published):
                return True

    if priv == 'exmo2010.answer_clarification_score':
        if user.is_active:
            if (profile.is_expertB and not profile.is_expertA) and not (monitoring.is_prepare or monitoring.is_published):
                return True

    return False


def organization_permission(user, priv, organization):
    """
    strange permission.
    don't know why we need see organization without tasks for this organization.
    don't use this. generate organization list from tasks list and exmo2010.view_task.

    """
    if priv == 'exmo2010.view_organization':
        if user.is_active:
            if user.profile.is_expertA or user.profile.is_manager_expertB:
                return True
            profile = user.profile
            if profile.is_expertB:
                if Task.objects.filter(organization=organization, user=user).count() > 0:
                    return True
            elif (profile.is_organization or profile.is_customer) and \
                            profile.organization.filter(pk=organization.pk).count() > 0:
                return True
    return False


def parameter_permission(user, priv, parameter):
    if priv == 'exmo2010.exclude_parameter':
        if user.is_active:
            if user.profile.is_expertA or user.profile.is_manager_expertB:
                return True
    return False


def check_permission(user, priv, context=None):
    """
    check user permission for context
    врапер для функций выше. точка входа для бекенда авторизации django
    делает eval на имя класса.

    """
    if context is None:
        return False
    func = eval(context._meta.object_name.lower() + '_permission')
    return func(user, priv, context)
