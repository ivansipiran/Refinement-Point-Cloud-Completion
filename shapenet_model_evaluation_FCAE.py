from dataset.ShapeNetDataset import *
from torch.utils.data import DataLoader
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
from losses.emd import emd_module as emd
from losses.chamfer import champfer_loss as chamfer
from models.FCAE_model import FCAEmodel
from utils.utils import weights_init, visdom_show_pc, save_paths, save_model, vis_curve
from utils.metrics import AverageValueMeter
from utils.pcutils import mean_min_square_distance, save_point_cloud
from losses.MDS import MDS_module


import sys

from extensions.chamfer_dist import ChamferDistance

class DevNull:
    def write(self, msg):
        pass

#Only for testing

parser = argparse.ArgumentParser()
parser.add_argument('--batchSize', type=int, default=1, help='input batch size')
parser.add_argument('--model', type=str, default = 'model',  help='optional reload model path')
parser.add_argument('--workers', type=int, help='number of data loading workers', default=12)
parser.add_argument('--num_points', type=int, default = 2048,  help='number of points')
parser.add_argument('--n_primitives', type=int, default = 16,  help='number of primitives')
parser.add_argument('--holeSize', type=int, default=35, help='hole size')
parser.add_argument('--outputFolder', type=str, default='', help='Folder output')
parser.add_argument('--inputTestFolder', type=str, default='', help='Input folder with test data')


opt = parser.parse_args()

# -------------------------------- Load network----------------------------------------
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    print("Using cuda device")
    torch.cuda.set_device(device)


network = FCAEmodel(1024, opt.num_points, opt.num_points).to(device)


network.apply(weights_init)
network.cuda()

#load model
print(opt.model, os.path.isfile(opt.model + "/model.pth"))

if opt.model != '' and os.path.isfile(opt.model + "/model.pth"):
    model_checkpoint = torch.load(opt.model + "/model.pth",map_location='cuda:0')
    
    print("Model network weights loaded ")
    network.model.load_state_dict(model_checkpoint['state_dict'])

print(f'**************************  FCAE - {opt.holeSize/100} ***********************************')

# Shapenet
n_models = 13
class_choice = {'Airplane': 0, 'Bag': 1, 'Cap': 2, 'Car': 3, 'Chair': 4, 'Guitar': 6, 'Lamp': 8, 'Laptop': 9, 'Motorbike': 10, 'Mug': 11, 'Pistol': 12, 'Skateboard': 14, 'Table': 15}
categories = class_choice.keys()

R = []

chamfer_dist = ChamferDistance()

L = []

#Reproducibility
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
torch.manual_seed(1)
torch.cuda.manual_seed_all(1)
np.random.seed(1)
random.seed(1)

for categorie in categories:

    pred_error = AverageValueMeter()
    gt_error = AverageValueMeter()
    chamfer_error = AverageValueMeter()


    dataset_dir = './data/shapenet_part'

    dataset_test = ShapeNetDataset(root_dir=dataset_dir, class_choice={categorie}, npoints=2048, split='test', hole_size=opt.holeSize/100)
    dataloader_test = DataLoader(dataset_test, batch_size=opt.batchSize, shuffle=False, num_workers=0)
    
    network.model.eval()
    
    with torch.no_grad():
        for i, data in enumerate(dataloader_test, 0):

            
            name, in_partial, in_hole, in_complete = data
            
            pathPartial = os.path.join(opt.inputTestFolder, categorie, name[0] + '_partial.xyz')
            pathComplete = os.path.join(opt.inputTestFolder, categorie, name[0] + '_gt.xyz')
            
            in_partial = np.loadtxt(pathPartial).astype(np.float32)
            in_complete = np.loadtxt(pathComplete).astype(np.float32)

            in_partial = torch.unsqueeze(torch.from_numpy(in_partial), 0)
            in_complete= torch.unsqueeze(torch.from_numpy(in_complete), 0)



            in_partial = in_partial.contiguous().float().to(device)
            in_complete = in_complete.contiguous().float().to(device)
            
            output2, rec_loss = network(in_partial, in_complete, 0.005, 50)
            
            dist = chamfer_dist(output2, in_complete)
            chamfer_error.update(dist.item()*10000)

            pred = output2.cpu().numpy()[0]
            gt = in_complete.cpu().numpy()[0]
            partial = in_partial.cpu().numpy()[0]
            
            pred_error.update(mean_min_square_distance(pred, gt)*10000)
            gt_error.update(mean_min_square_distance(gt, pred)*10000)

            if opt.outputFolder != "":
                #Save models and metric
                log_table = {"name":name, "chamfer": dist.item()*10000}
                L.append(log_table)
                #print(name)
                save_point_cloud(os.path.join(opt.outputFolder, categorie, name[0]+'_gt.xyz'), gt)
                save_point_cloud(os.path.join(opt.outputFolder, categorie, name[0]+'_partial.xyz'), partial)
                save_point_cloud(os.path.join(opt.outputFolder, categorie, name[0]+'_pred.xyz'), pred)
            
        
        gt_error.end_epoch() 
        pred_error.end_epoch()
        chamfer_error.end_epoch()
    
    if opt.outputFolder != "":
        with open(os.path.join(opt.outputFolder, categorie+".txt"), 'w') as fi:
            fi.write(json.dumps(L))
    
    R.append({'cat': categorie, 'chamfer': chamfer_error.avg, 'pred': pred_error.avg, 'gt':gt_error.avg})  

print('Categorie:', end='\t')
print('Chamfer:', end='\t')
print('Pred->GT:', end='\t')
print('GT->Pred:', end='\t')
print()

for dc in R:
    print(dc['cat'], end='\t')    
    print(dc['chamfer'], end='\t')
    print(dc['pred'], end='\t')
    print(dc['gt'], end='\t')
    print()