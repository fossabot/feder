from atom.views import (
    ActionMessageMixin,
    ActionView,
    CreateMessageMixin,
    DeleteMessageMixin,
    UpdateMessageMixin
)
from braces.views import (
    FormValidMessageMixin,
    PrefetchRelatedMixin,
    SelectRelatedMixin,
    UserFormKwargsMixin
)
from cached_property import cached_property
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_filters.views import FilterView

from feder.cases.models import Case
from feder.main.mixins import AttrPermissionRequiredMixin, RaisePermissionRequiredMixin

from .filters import TaskFilter
from .forms import AnswerFormSet, SurveyForm, TaskForm
from .models import Survey, Task

DONE_MESSAGE_TEXT = _("Already done the job. If you want to change the answer - delete answers.")

THANK_TEXT = _("Thank you for your submission. It is approaching us to know the " +
               "truth, by obtaining reliable data.")

EXHAUSTED_TEXT = _("Thank you for your help. Unfortunately, all the tasks " +
                   "for you have been exhausted.")


class TaskListView(SelectRelatedMixin, FilterView):
    filterset_class = TaskFilter
    model = Task
    select_related = ['case', 'questionary']
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super(TaskListView, self).get_context_data(**kwargs)
        context['stats'] = self.object_list.survey_stats()
        return context


class TaskDetailView(SelectRelatedMixin, PrefetchRelatedMixin, DetailView):
    model = Task
    select_related = ['case__monitoring', 'case__institution', 'questionary']
    prefetch_related = ['survey_set', 'questionary__question_set']

    def get_context_data(self, *args, **kwargs):
        context = super(TaskDetailView, self).get_context_data(*args, **kwargs)
        context['formset'] = AnswerFormSet(survey=None, questionary=self.object.questionary)
        try:
            context['user_survey'] = (self.object.survey_set.with_full_answer().
                                      filter(user=self.request.user.pk).get())
        except Survey.DoesNotExist:
            context['user_survey'] = None
        return context


class TaskSurveyView(SelectRelatedMixin, PrefetchRelatedMixin, DetailView):
    model = Task
    select_related = ['case__monitoring', 'case__institution', 'questionary', ]
    prefetch_related = ['questionary__question_set']
    template_name_suffix = '_survey'

    def get_context_data(self, *args, **kwargs):
        context = super(TaskSurveyView, self).get_context_data(*args, **kwargs)
        survey_list = (Survey.objects.for_task(self.object).with_user().with_full_answer().all())
        context['survey_list'] = survey_list
        user_survey_list = [x for x in survey_list if x.user == self.request.user]  # TODO: Lazy
        context['user_survey'] = user_survey_list[0] if user_survey_list else None
        return context


class TaskCreateView(RaisePermissionRequiredMixin, UserFormKwargsMixin,
                     CreateMessageMixin, CreateView):
    model = Task
    form_class = TaskForm
    permission_required = 'monitorings.add_task'

    @cached_property
    def case(self):
        return get_object_or_404(Case.objects.select_related('monitoring'),
                                 pk=self.kwargs['case'])

    def get_permission_object(self):
        return self.case.monitoring

    def get_form_kwargs(self, *args, **kwargs):
        kw = super(TaskCreateView, self).get_form_kwargs(*args, **kwargs)
        kw['case'] = self.case
        return kw

    def get_context_data(self, *args, **kwargs):
        context = super(TaskCreateView, self).get_context_data(*args, **kwargs)
        context['case'] = self.case
        return context


class TaskUpdateView(AttrPermissionRequiredMixin, UserFormKwargsMixin,
                     UpdateMessageMixin, FormValidMessageMixin, UpdateView):
    model = Task
    form_class = TaskForm
    permission_required = 'change_task'
    permission_attribute = 'case__monitoring'


class TaskDeleteView(AttrPermissionRequiredMixin, DeleteMessageMixin, DeleteView):
    model = Task
    success_url = reverse_lazy('tasks:list')
    permission_required = 'delete_task'
    permission_attribute = 'case__monitoring'


class SurveyDeleteView(DeleteMessageMixin, DeleteView):
    model = Survey
    slug_url_kwarg = 'task_id'
    slug_field = 'task_id'

    def get_queryset(self, *args, **kwargs):
        qs = super(SurveyDeleteView, self).get_queryset(*args, **kwargs)
        return qs.filter(user=self.request.user).with_full_answer()

    def get_success_url(self):
        return self.object.task.get_absolute_url()


class SurveySelectView(AttrPermissionRequiredMixin, ActionMessageMixin,
                       SelectRelatedMixin, ActionView):  # TODO: Write test
    model = Survey
    template_name_suffix = '_select'
    select_related = ['task__case__monitoring', ]
    permission_required = 'monitorings.select_survey'
    permission_attribute = 'task__case__monitoring'
    direction = None
    change = {'up': 1, 'down': -1}

    def action(self, *args, **kwargs):
        self.object.credibility_update(self.change[self.direction])
        self.object.save()

    def get_success_message(self):
        return _("Survey {object} selected!").format(object=self.object)

    def get_success_url(self):
        return reverse('tasks:survey', kwargs={'pk': self.object.task_id})


@login_required
def fill_survey(request, pk):  # TODO: Convert to CBV eg. TemplateView
    context = {}
    task = get_object_or_404(Task, pk=pk)
    context['object'] = task
    if Survey.objects.filter(task=task, user=request.user).exists():
        messages.warning(request, DONE_MESSAGE_TEXT)
        return redirect(task)
    form = SurveyForm(data=request.POST or None,
                      task=task,
                      user=request.user)
    context['form'] = form
    if request.POST and form.is_valid():
        obj = form.save(commit=False)
        formset = AnswerFormSet(data=request.POST or None,
                                survey=obj,
                                questionary=task.questionary)
        context['formset'] = formset
        if formset.is_valid():
            messages.success(request, THANK_TEXT)
            obj.save()
            formset.save()
            if 'save' in request.POST:
                return redirect(obj.task)
            else:
                next_task = task.get_next_for_user(request.user)
                if next_task:
                    return redirect(next_task)
                else:
                    messages.success(request, EXHAUSTED_TEXT)
                    return redirect(task.case.monitoring)
    else:
        formset = AnswerFormSet(data=request.POST or None, questionary=task.questionary)
        context['formset'] = formset
    return render(request, 'tasks/task_fill.html', context)
