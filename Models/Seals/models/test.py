
import sys
import random
import math

from tools.model import io

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

from detection import box, anchors, display, evaluate, loss
import argparse

from detection.models import models
from tools.image import cv


def random_box(dim, num_classes):
    cx = random.uniform(0, dim[0])
    cy = random.uniform(0, dim[1])

    sx = random.uniform(0.1, 0.2) * dim[0]
    sy = random.uniform(0.1, 0.2) * dim[1]
    return (cx, cy, sx, sy)


if __name__ == '__main__':

    random.seed(0)
    torch.manual_seed(0)

    parser = argparse.ArgumentParser(description='Test model')

    parser.add_argument('--model', action='append', default=[],
                        help='model type and sub-parameters e.g. "unet --dropout 0.1"')

    args = parser.parse_args()

    print(args)

    num_classes = 2
    model_args = {'num_classes':num_classes, 'input_channels':3}

    creation_params = io.parse_params(models, args.model)
    model, encoder = io.create(models, creation_params, model_args)

    print(model)

    batches = 1
    dim = (512, 512)

    images = Variable(torch.FloatTensor(batches, 3, dim[1], dim[0]).uniform_(0, 1))
    loc_preds, class_preds = model.cuda()(images.cuda())


    def random_target():
        num_boxes = random.randint(1, 50)
        boxes = torch.Tensor ([random_box(dim, num_classes) for b in range(0, num_boxes)])
        boxes = box.point_form(boxes)
        label = torch.LongTensor(num_boxes).random_(0, num_classes)
        return (boxes, label)

    target_boxes = [random_target() for i in range(0, batches)]
    target =  [encoder.encode(dim, boxes, label) for boxes, label in target_boxes]

    loc_target = Variable(torch.stack([loc for loc, _ in target]).cuda())
    class_target = Variable(torch.stack([classes for _, classes in target]).cuda())

    # print((loc_target, class_target), (loc_preds, class_preds))

    print(loss.total_loss( (loc_target, class_target), (loc_preds, class_preds) ))

    detections = encoder.decode_batch(images.detach(), loc_preds.detach(), class_preds.detach())

    classes = {}
    for i, (boxes, label, confs), (target_boxes, target_label) in zip(images.detach(), detections, target_boxes):
        score = evaluate.mAP(boxes, label, confs, target_boxes.type_as(boxes), target_label.type_as(label), threshold = 0.1)

        print(score)

        # noise = target_boxes.clone().uniform_(-20, 30)
        # score = evaluate.mAP(target_boxes + noise, target_label, torch.arange(target_label.size(0)), target_boxes, target_label, threshold=0.5)
        # print(score)




        # i = i.permute(1, 2, 0)
        # key = cv.display(display.overlay(i, boxes, label, confidence=confs))
        # if(key == 27):
        #     break



    #print(boxes)


    #loss = MultiBoxLoss(num_classes)
    #target = (Variable(boxes.cuda()), Variable(label.cuda()))

    #print(loss(out, target))
