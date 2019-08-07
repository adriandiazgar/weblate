# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2019 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from __future__ import unicode_literals

from django.core.checks import run_checks
from django.shortcuts import redirect, render
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from weblate.auth.decorators import management_access
from weblate.trans.models import Component
from weblate.utils import messages
from weblate.utils.errors import report_error
from weblate.utils.views import show_form_errors
from weblate.vcs.ssh import (
    add_host_key,
    can_generate_key,
    generate_ssh_key,
    get_host_keys,
    get_key_data,
)
from weblate.wladmin.forms import ActivateForm
from weblate.wladmin.models import ConfigurationError, SupportStatus

MENU = (
    (
        'index',
        'manage',
        ugettext_lazy('Weblate status'),
    ),
    (
        'memory',
        'manage-memory',
        ugettext_lazy('Translation memory'),
    ),
)


@management_access
def manage(request):
    support = SupportStatus.objects.get_current()
    return render(
        request,
        "manage/index.html",
        {
            'menu_items': MENU,
            'menu_page': 'index',
            'support': support,
            'activate_form': ActivateForm(),
        }
    )


@management_access
def activate(request):
    form = ActivateForm(request.POST)
    if form.is_valid():
        support = SupportStatus(**form.cleaned_data)
        try:
            support.refresh()
            if not support.expiry:
                raise Exception('expired')
            support.save()
            messages.error(request, _('Activation completed.'))
        except Exception as error:
            report_error(error, request)
            messages.error(
                request,
                _('The activation failed. Please check your activation token.')
            )
    else:
        show_form_errors(request, form)
    return redirect('manage')


def report(request, admin_site):
    """Provide report about git status of all repos."""
    context = admin_site.each_context(request)
    context['components'] = Component.objects.order_project()
    return render(
        request,
        "admin/report.html",
        context,
    )


def handle_dismiss(request):
    try:
        error = ConfigurationError.objects.get(
            pk=int(request.POST['pk'])
        )
        if 'ignore' in request.POST:
            error.ignored = True
            error.save(update_fields=['ignored'])
        else:
            error.delete()
    except (ValueError, KeyError, ConfigurationError.DoesNotExist):
        messages.error(request, _('Failed to dismiss configuration error!'))
    return redirect('admin:performance')


def performance(request, admin_site):
    """Show performance tuning tips."""
    if request.method == 'POST':
        return handle_dismiss(request)

    context = admin_site.each_context(request)
    context['checks'] = run_checks(include_deployment_checks=True)
    context['errors'] = ConfigurationError.objects.filter(ignored=False)

    return render(
        request,
        "admin/performance.html",
        context,
    )


def ssh(request, admin_site):
    """Show information and manipulate with SSH key."""
    # Check whether we can generate SSH key
    can_generate = can_generate_key()

    # Grab action type
    action = request.POST.get('action')

    # Generate key if it does not exist yet
    if can_generate and action == 'generate':
        generate_ssh_key(request)

    # Read key data if it exists
    key = get_key_data()

    # Add host key
    if action == 'add-host':
        add_host_key(
            request,
            request.POST.get('host', ''),
            request.POST.get('port', '')
        )

    context = admin_site.each_context(request)
    context['public_key'] = key
    context['can_generate'] = can_generate
    context['host_keys'] = get_host_keys()

    return render(
        request,
        "admin/ssh.html",
        context,
    )
