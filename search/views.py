import requests
from django.conf import settings
from django.shortcuts import render
from .forms import SortMethod
from django.views.decorators.cache import cache_control, never_cache
from django.http import HttpResponseRedirect
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator

session_key = ''


# Create your views here.
@cache_control(no_cache=True, must_revalidate=False, no_store=True)
def index(request):
    # request connection to YoutubeAPI different part
    comment_url = 'https://www.googleapis.com/youtube/v3/commentThreads'
    channel_url = 'https://www.googleapis.com/youtube/v3/channels'

    # initialize the data structures
    form = SortMethod()
    err_message = ''
    comments = []
    channel = ''
    searchTerms = ''
    sort = ''
    channelID = ''
    context = {
        'comments': [],
        'form': form,
        'err_message': err_message
    }
    # process front-end inputs and interact with back-end
    if request.method == 'POST':
        form = SortMethod(request.POST)
        if form.is_valid():
            channel = form.cleaned_data['channel']
            searchTerms = form.cleaned_data['comment']
            sort = form.cleaned_data['sort']

    elif request.GET.get('channel', '') and request.GET.get('searchTerms', ''):
        channel = request.GET['channel']
        searchTerms = request.GET['searchTerms']

    if channel != '' and searchTerms != '':
        # get channel parameters
        getChannel_params = {
            'part': 'id',
            'forUsername': channel,
            'key': settings.YOUTUBE_API_KEY
        }

        r = requests.get(channel_url, params=getChannel_params)
        channelID = r.json().get('items')

        # error check for channel
        if channelID is None:
            if r.json().get('pageInfo') is not None:
                err_message = 'Channel Name Not Found'
                context = {
                    'comments': [],
                    'form': form,
                    'err_message': err_message
                }
                return render(request, 'search/index.html', context)

            else:
                err_message = 'Network Problem!'
                context = {
                    'comments': [],
                    'form': form,
                    'err_message': err_message
                }
                return render(request, 'search/index.html', context)

        else:
            channelID = channelID[0]['id']

        # comment parameter
        comment_params = {
            'part': 'snippet',
            'allThreadsRelatedToChannelId': channelID,
            'searchTerms': searchTerms,
            'order': 'time',
            'maxResults': 100,
            'key': settings.YOUTUBE_API_KEY
        }

        r = requests.get(comment_url, params=comment_params)
        # error check for comment
        comment_results = r.json().get('items')
        # close
        if comment_results is None:
            print(r.json())
            err_message = 'Comments have been closed for this channel'
            context = {
                'comments': [],
                'form': form,
                'err_message': err_message
            }
            return render(request, 'search/index.html', context)
        # comment not exist
        if len(comment_results) == 0:
            err_message = 'Comments Not Found!'
            context = {
                'comments': [],
                'form': form,
                'err_message': err_message
            }
            return render(request, 'search/index.html', context)

        if 'nextPageToken' in r.json():
            nextPageToken = r.json()['nextPageToken']
        else:
            nextPageToken = ''
        # add comment results
        for comment in comment_results:
            comment_data = {
                'comment': comment['snippet']['topLevelComment']['snippet']['textDisplay'],
                'video': comment['snippet']['topLevelComment']['snippet'].get('videoId'),
                'likeCount': comment['snippet']['topLevelComment']['snippet']['likeCount'],
                'avatar': comment['snippet']['topLevelComment']['snippet']['authorProfileImageUrl']
            }
            comments.append(comment_data)

        while nextPageToken != '':
            comment_params.update({'pageToken': nextPageToken})
            r = requests.get(comment_url, params=comment_params)

            if 'nextPageToken' in r.json():
                nextPageToken = r.json()['nextPageToken']
            else:
                nextPageToken = ''

            comment_results = r.json().get('items')
            if comment_results is not None:
                for comment in comment_results:
                    comment_data = {
                        'comment': comment['snippet']['topLevelComment']['snippet']['textDisplay'],
                        'video': comment['snippet']['topLevelComment']['snippet'].get('videoId'),
                        'likeCount': comment['snippet']['topLevelComment']['snippet']['likeCount'],
                        'avatar': comment['snippet']['topLevelComment']['snippet']['authorProfileImageUrl']
                    }
                    comments.append(comment_data)

        comments = calculateRelevance(comments, list(searchTerms.split(" ")))
        if sort == 'like':
            comments = sorted(comments, key=lambda i: i['like_score'], reverse=True)
        elif sort == 'relevance':
            comments = sorted(comments, key=lambda i: i['score'], reverse=True)
        else:
            comments = sorted(comments, key=lambda i: i['score'] * i['like_score'], reverse=True)

        s = SessionStore()
        s['searchTerms'] = searchTerms
        s['comments'] = comments
        s['channel'] = channel
        s.create()
        global session_key
        session_key = s.session_key

        return HttpResponseRedirect("/result")

    return render(request, 'search/index.html', context)


def calculateRelevance(comments, query_terms):
    collection_length = 0
    gamma = 0.9
    # store score
    score_list = [1 for i in range(len(comments))]
    # store likeCount
    likes_list = []

    for i in comments:
        tmp = 0
        likes_list.append(i['likeCount'])
        collection_length = collection_length + len(list(i['comment'].split(" ")))

    for term in query_terms:
        doc_f = []
        terms_f = 0
        tf = 0
        for i in comments:
            f = 0
            for word in list(i['comment'].lower().split(" ")):
                if term.lower() in word:
                    tf = tf + 1
                    f = f + 1
            doc_f.append(f / len(list(i['comment'].split(" "))))
        terms_f = tf / collection_length

        for i in range(len(comments)):
            # Linear interpolation Smoothing
            score = gamma * terms_f + (1 - gamma) * doc_f[i]
            # score1*score2*score3......
            score_list[i] = score_list[i] * score

    # normalized parameter
    for i in range(len(comments)):
        comments[i].update({'score': (score_list[i] - min(score_list)) / (max(score_list) - min(score_list))})
        comments[i].update({'like_score': (likes_list[i] - min(likes_list) + 1) / (max(likes_list) - min(likes_list))})

    return comments


def result(request):
    global session_key
    s = SessionStore(session_key=session_key)
    comments = s['comments']
    form = SortMethod()
    channel = s['channel']
    searchTerms = s['searchTerms']
    sort = ''

    # three different sorting methods
    if request.GET.get('sort', ''):
        # default = like * relevance
        if request.GET['sort'] == 'default':
            sort = 'default'
            comments = sorted(comments, key=lambda i: i['score'] * i['like_score'], reverse=True)
        # relevance
        elif request.GET['sort'] == 'relevance':
            sort = 'relevance'
            comments = sorted(comments, key=lambda i: i['score'], reverse=True)
        # likeCount
        else:
            sort = 'like'
            comments = sorted(comments, key=lambda i: i['like_score'], reverse=True)

    if request.method == 'POST':
        form = SortMethod(request.POST)
        if form.is_valid():
            channel = form.cleaned_data['channel']
            searchTerms = form.cleaned_data['comment']
            # print(form.cleaned_data)
            Session.objects.all().delete()
            return HttpResponseRedirect("/?" + "&channel=" + channel + "&searchTerms=" + searchTerms)

    # Show 9 results per page
    paginator = Paginator(comments, 9)
    page = request.GET.get('page')
    comments_page = paginator.get_page(page)

    context = {
        'comments': comments_page,  # comments[:9],
        'form': form,
        'sort': sort,
        'searchTerms': searchTerms,
        'channel': channel
    }

    return render(request, 'search/result.html', context)
