from django.urls import path

from coaching.views import (
    AssignCoachView, ClientQuestionnaireView, CoachesView, InviteCardView,
    JoinView,
    MyApplicationInviteView, MyApplicationsView, MyApplicationView,
    MyClientsView, MyInviteView,
)

urlpatterns = [
    path('coach/invite/', MyInviteView.as_view(), name='coach-invite'),
    path('coach/invite/<str:code>/', InviteCardView.as_view(),
         name='coach-invite-card'),
    path('coach/join/', JoinView.as_view(), name='coach-join'),
    path('coach/assign/', AssignCoachView.as_view(), name='coach-assign'),
    path('coach/clients/', MyClientsView.as_view(), name='coach-clients'),
    path('coach/clients/<str:username>/questionnaire/',
         ClientQuestionnaireView.as_view(), name='coach-client-questionnaire'),
    path('coach/applications/', MyApplicationsView.as_view(),
         name='coach-applications'),
    path('coach/applications/<int:pk>/', MyApplicationView.as_view(),
         name='coach-application'),
    path('coach/applications/<int:pk>/invite/',
         MyApplicationInviteView.as_view(), name='coach-application-invite'),
    path('coaches/', CoachesView.as_view(), name='coaches'),
]
