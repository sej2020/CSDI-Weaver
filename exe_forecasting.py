import argparse
import torch
import datetime
import json
import yaml
import os

from main_model import CSDI_Forecasting
from dataset_forecasting import get_dataloader
from utils import train, evaluate

parser = argparse.ArgumentParser(description="CSDI")
parser.add_argument("--config", type=str, default="base_forecasting.yaml")
parser.add_argument("--datatype", type=str, default="electricity")
parser.add_argument('--device', default='cuda:0', help='Device for Attack')
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--pseudo_unconditional", action="store_true")
parser.add_argument("--true_unconditional", action="store_true")
parser.add_argument("--modelfolder", type=str, default="")
parser.add_argument("--nsample", type=int, default=100)
parser.add_argument("--time_weaver", action="store_true")
parser.add_argument("--history_length", type=int, default=168)
parser.add_argument("--n_condit_features", type=int, default=-1)
parser.add_argument("--condit_strat", type=str, default="pca")

args = parser.parse_args()
print(args)

path = "config/" + args.config
with open(path, "r") as f:
    config = yaml.safe_load(f)

if args.datatype == 'electricity':
    target_dim = 370

if args.n_condit_features == 0:
    print("When n_condit_features is 0, it is the same as true_unconditional. Setting true_unconditional to True, and ignoring n_condit_features")
    args.true_unconditional = True
    args.n_condit_features = -1

config["model"]["is_pseudo_unconditional"] = args.pseudo_unconditional
config["model"]["is_true_unconditional"] = args.true_unconditional
config["model"]["history_length"] = args.history_length
config["model"]["n_condit_features"] = args.n_condit_features
config["model"]["condit_strat"] = args.condit_strat

assert not (args.pseudo_unconditional and args.true_unconditional), "Cannot be both pseudo and true unconditional"
assert not ((args.pseudo_unconditional or args.true_unconditional) and args.n_condit_features > 0), "Cannot be unconditional and have conditional features"
assert not args.n_condit_features > config["model"]["num_sample_features"], "Cannot have more conditional features than sample features"

print(json.dumps(config, indent=4))

if args.modelfolder:
    foldername = "./save/" + args.modelfolder
    config = json.load(open(foldername + "/config.json"))
    if config["weaver"]["included"]:
        args.time_weaver = True
else:
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    foldername = "./save/testing_" + current_time + "/"
    # foldername = "./save/forecasting_" + args.datatype + '_' + current_time + "/"
    # foldername = "./save/hist_len_expr/fc_" + str(args.history_length) + '_' + current_time + "/"
    # foldername = "./save/feature_num_expr_pca/fc_" + str(args.n_condit_features) + '_' + current_time + "/"
    print('model folder:', foldername)
    os.makedirs(foldername, exist_ok=True)
    with open(foldername + "config.json", "w") as f:
        json.dump(config, f, indent=4)


train_loader, valid_loader, test_loader, scaler, mean_scaler = get_dataloader(
    datatype=args.datatype,
    device= args.device,
    batch_size=config["train"]["batch_size"],
    time_weaver=args.time_weaver,
    true_unconditional=args.true_unconditional,
    history_length=args.history_length,
    n_condit_features=args.n_condit_features,
    condit_strat=args.condit_strat
)
if args.time_weaver:
    config["weaver"]["included"] = True
    config["weaver"]["k_meta"] = train_loader.dataset.metadata.shape[1]


if not args.modelfolder:
    with open(foldername + "config.json", "w") as f:
        json.dump(config, f, indent=4)

model = CSDI_Forecasting(config, args.device, target_dim, time_weaver=args.time_weaver, n_condit_features=args.n_condit_features).to(args.device)

if args.modelfolder == "":
    train(
        model,
        config["train"],
        train_loader,
        valid_loader=valid_loader,
        scaler=scaler,
        mean_scaler=mean_scaler,
        foldername=foldername,
    )
else:
    model.load_state_dict(torch.load("./save/" + args.modelfolder + "/model.pth", weights_only=True))
model.target_dim = target_dim

evaluate(
    model,
    test_loader,
    nsample=args.nsample,
    scaler=scaler,
    mean_scaler=mean_scaler,
    foldername=foldername,
)
