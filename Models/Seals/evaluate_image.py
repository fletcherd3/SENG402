import numpy as np
import cv2

import torch

from tools import struct, pprint_struct
from tools.parameters import param, parse_args

from tools.image import cv
from checkpoint import load_model

from evaluate import evaluate_image
from detection import box, display, detection_table

parameters = struct (
    model = param('',  required = True,     help = "model checkpoint to use for detection"),
    input = param('',    required = True,   help = "input image"),

    threshold = param(0.5, "detection threshold")
)


args = parse_args(parameters, "image evaluation", "image evaluation parameters")
device = torch.cuda.current_device()

model, encoder, model_args = load_model(args.model)
print("model parameters:")
pprint_struct(model_args)

classes = model_args.dataset.classes

model.to(device)
encoder.to(device)

frame = cv.imread_color(args.input)

nms_params = detection_table.nms_defaults._extend(nms = args.threshold)
pprint_struct(nms_params)

results = evaluate_image(model, frame, encoder, nms_params = nms_params, device=device)

d, p = results.detections, results.prediction
detections = zip(d.index, d.label, d.bbox, d.confidence)
predictions = zip(p[0], p[1])

for index, label, bbox, confidence in detections:
    if confidence > 0.7:
        label_class = classes[label]
        display.draw_box(frame, bbox, confidence=confidence, 
            name=label_class.name, color=display.to_rgb(label_class.colour))



# for prediction in results.detections:
    
#     if prediction.confidence > 0.7:
#         label_class = classes[prediction.label].name
#         display.draw_box(frame, prediction.bbox, confidence=prediction.confidence, 
#             name=label_class.name, color=display.to_rgb(label_class.colour))

frame = cv.resize(frame, (frame.size(1) // 2,  frame.size(0) // 2))
cv.display(frame)
    

