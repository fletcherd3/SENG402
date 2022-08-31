import torch.nn as nn


def create(models, model_args, dataset_args):
    assert model_args.choice in models, "model not found " + model_args.choice
    model = models[model_args.choice]

    return model.create(model_args.parameters, dataset_args)


def model_stats(model):
    convs = 0
    for m in model.modules():
        if isinstance(m, nn.Conv2d) or isinstance(m, nn.ConvTranspose2d):
            convs += 1

    parameters = sum([p.nelement() for p in model.parameters()])
    print("Model of {} parameters, {} convolutions".format(parameters, convs))

# def merge_state_dict(model, loaded):
