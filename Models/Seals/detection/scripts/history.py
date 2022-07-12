
import json
from dataset import annotate
from os import path

import argparse

from tools import table, struct, to_structs, filter_none, drop_while, \
     concat_lists, map_dict, sum_list, pluck, count_dict, partition_by, shape, Struct, transpose_structs

from detection import evaluate

from collections import deque

import tools

from scripts.datasets import quartiles, stats

from evaluate import compute_AP

import dateutil.parser as date

from matplotlib import rc
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import numpy as np
import torch


def decode_action(action):
    if action.tag == 'undo':
        return struct(action = 'undo')

    elif action.tag == 'redo':
        return struct(action = 'redo')

    elif action.tag == 'threshold':
        return struct(action = 'threshold', value=action.contents)        

    elif action.tag == 'close':
        return struct(action='submit')

    elif action.tag == 'edit':
        edit = action.contents

        if edit.tag == 'confirm_detection':
            return struct(action='confirm', ids = list(edit.contents.keys()))

        elif edit.tag == 'transform_parts':
            transform, ids =  edit.contents
            s, t = transform

            return struct(action='transform', t = 'translate', ids = list(ids.keys()))
        elif edit.tag == 'add':
            
            return struct(action='add')
        elif edit.tag == 'delete_parts':

            ids = list(edit.contents.keys())

            return struct(action='delete', ids = ids)


        elif edit.tag == 'clear_all':

            return struct(action='delete')

        elif edit.tag == 'set_class':
            class_id, ids = edit.contents
            return struct(action='set_class', ids = ids, class_id = class_id)
        
        else:
            assert False, "unknown edit type: " + edit.tag


    else:
        assert False, "unknown action type: " + action.tag


empty_detections = table (
        bbox = torch.FloatTensor(0, 4),
        label = torch.LongTensor(0),
        confidence = torch.FloatTensor(0))

def extract_session(session, config):

    start = date.parse(session.time)
    detections = []
    actions = []

  
    detections = annotate.decode_detections(session.open.contents.instances, annotate.class_mapping(config)) \
        if session.open.tag == "new" else empty_detections

    def previous():
        return actions[-1] if len(actions) > 0 else None

    def previous_time():        
        return (actions[-1].time if len(actions) > 0 else 0)

    for (datestr, action) in session.history:
        t = date.parse(datestr)
        action = decode_action(action)

        prev = previous()
        if prev and action.action in ['transform', 'delete']:
            if prev.action == 'confirm' and prev.ids == action.ids:
                actions.pop()

        time = (t - start).total_seconds()    
        duration = time - previous_time()
        actions.append(action._extend(time = time, duration = min(30, duration), real_duration = duration))        

    duration = sum (pluck('duration', actions))
    end = actions[-1].time

    return struct(start = start, detections = detections, actions = actions, \
        duration = duration, real_duration = end,  type = session.open.tag, threshold=session.threshold)


def action_durations(actions):
    return [action.duration for action in actions if action.duration > 0]


def image_summaries(history):
    return [image_summary(image) for image in history]




correction_types = ['positive', 'modified positive', 'weak positive', 'false negative', 'false positive']
action_types = ['transform', 'confirm', 'add', 'delete', 'submit', 'set_class']



def annotation_corrections(image):
    mapping = {'add':'false negative', 'confirm':'weak positive', 'detect':'positive'}
    t = image.threshold

    def get_category(s):
        if s.status.tag == "active":
            if s.created_by.tag == "detect":
                return "modified positive" if (s.changed_class or s.transformed) else "positive"
            return mapping.get(s.created_by.tag)

        if s.created_by.tag == "detect" and s.status.tag == "deleted":
            detection = s.created_by.contents
            if detection.confidence >= t:
                return "false positive"

    created = filter_none([get_category(s) for s in image.ann_summaries])
    return count_struct(created, correction_types)

def image_summary(image):
   
    return struct (
        actions = image.actions,
        n_actions = len(image.actions), 
        duration = image.duration,
         
        real_duration = image.real_duration,
        instances = image.target._size,
        actions_count = count_struct(pluck('action', image.actions), action_types),
        correction_count = annotation_corrections(image)
    )


def image_summaries(history):
    summaries = [image_summary(image) for image in history]

    durations = pluck('duration', summaries)
    cumulative_time = np.cumsum(durations)

    return [summary._extend(cumulative_time = t) for summary, t in zip(summaries, cumulative_time)]


def count_struct(values, keys):
    d = count_dict(values)
    return Struct({k:d.get(k, 0) for k in keys})


    

def history_summary(history):
    
    summaries = image_summaries(history)
    totals = sum_list(summaries)
    n = len(history)

    summaries = transpose_structs(summaries)
    actions = transpose_structs([actions._subset('action', 'duration', 'real_duration') for actions in totals.actions])

    actions_count = count_struct(actions.action, action_types)
    total_actions = sum(actions_count.values(), 0)

    return summaries, struct (
        action_durations = stats(actions.duration),
        action_real_durations = stats(actions.real_duration),

        annotation_breaks = len([action.real_duration for action in totals.actions if action.real_duration > 60]),

        image_durations = stats(summaries.duration),

        n_actions =  stats(summaries.n_actions),
        instances_image = stats(summaries.instances),

        correction_count = totals.correction_count,
        actions_count = totals.actions_count,

        total_minutes = totals.duration / 60,
        total_actions = total_actions,

        actions_minute      = 60 * total_actions / totals.duration,
        instances_minute    = 60 * totals.instances / totals.duration,

        actions_annotation = total_actions / totals.instances
    )
        

def extract_image(image, config):
    target = annotate.decode_image(image, config).target

    if image.category in ['validate', 'train'] and len(image.sessions) > 0:          
        session = extract_session(image.sessions[0], config)
    
        return struct (
            filename = image.image_file,
            start = session.start,
            detections = session.detections,
            duration = session.duration,
            real_duration = session.real_duration,
            actions = session.actions,
            threshold = session.threshold,
            ann_summaries = image.summaries,
            target = target)
        

def extract_histories(dataset):
    images = [extract_image(image, dataset.config) for image in dataset.images]
    images = sorted(filter_none(images), key = lambda image: image.start)

    return images
