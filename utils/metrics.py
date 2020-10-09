class AverageValueMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.avgs = []
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0.0
        
    def end_epoch(self):
        self.avgs = self.avgs + [self.avg]
        self.val = 0
        # self.avg = 0
        self.sum = 0
        self.count = 0.0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count