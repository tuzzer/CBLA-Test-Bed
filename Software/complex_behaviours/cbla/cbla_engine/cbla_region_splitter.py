import random
import numpy as np
import math
import bisect
import statistics as stat
from time import perf_counter

from sklearn.cluster import KMeans
from sklearn.cluster import Ward
#from sklearn.decomposition import PCA
from sklearn.decomposition import KernelPCA as PCA
from sklearn.decomposition import FastICA as ICA
from sklearn.neighbors import KNeighborsClassifier as knn
from sklearn.svm import SVC
from sklearn.svm import SVR
from sklearn.cross_validation import KFold
from sklearn import metrics
from sklearn import linear_model


class RegionSplitter():

    def __init__(self, data, label):

        t0 = perf_counter()
        self.cut_dim = 0
        self.cut_val = 0

        data_dim_num = len(data[0])
        label_dim_num = len(label[0])

        num_candidates = 10

        sample = list(zip(data, label))

        # storage while calculating the best
        best_score = -float("inf")
        # [group_size_diff, var_reduction, cut_dim, cut_val]
        best_cut_arr = [(-float("inf"), self.cut_dim, self.cut_val)]

        # calculate the minimum of the overall variance
        #TODO figure out the best way to compare  multi-D variance
        overall_var = min(np.var(label, axis=0, ddof=1))

        # if all are the same, split quality is -inf (shouldn't be split at all)
        if overall_var <= 0:
            self.__split_quality = -float('inf')

        else:

            # sort in each dimension
            for i in range(data_dim_num):

                # sort the data in dimension i
                sorted_samples = sorted(sample, key=lambda x: x[0][i])
                # separate the data back into data and label again
                sorted_dim_data = [sample[0][i] for sample in sorted_samples]
                sorted_label = [sample[1] for sample in sorted_samples]

                for k in range(num_candidates):
                    # pick a random value
                    max_val = sorted_dim_data[-1]
                    min_val = sorted_dim_data[0]
                    cut_val = random.uniform(min_val, max_val)

                    # calculate the cut index
                    cut_idx = bisect.bisect_left(sorted_dim_data, cut_val)
                    groups = [sorted_label[:cut_idx], sorted_label[cut_idx:]]

                    # check if any of the group is too small
                    if len(groups[0]) < data_dim_num or len(groups[1]) < data_dim_num:
                        continue

                    variances = []
                    for group in groups:
                        # calculate the in-group variance
                        variances.append(min(np.var(group, axis=0, ddof=1)))
                    # take the smallest variance
                    avg_var = stat.mean(variances)

                    # negate the variance and plus 1
                    # (we want low relative variance worst should be 1)
                    score = -avg_var

                    # split quality is relative variance to the original
                    quality = 1 - avg_var/overall_var

                    if score > best_score:

                        best_score = score
                        best_cut_arr = [(quality, i, cut_val),]

                    elif score == best_score:
                        best_cut_arr.append((quality, i, cut_val))

                    else:
                        pass

            # sorting the best cut array with smallest group_size_diff at the front
            best_cut_arr = sorted(best_cut_arr, key=lambda x: x[0])

            # the best cut_dim is the one with the smallest group_size_diff
            self.cut_dim = best_cut_arr[0][1]
            self.cut_val = best_cut_arr[0][2]

            # the best split quality
            self.__split_quality = best_cut_arr[0][0]
        #print(self.__split_quality, ', ')
        split_clock = perf_counter() - t0
        if split_clock > 1:
            print(split_clock)
        # just cut in half
        # self.cut_val = exemplars[int(sample_num/2)][0][self.cut_dim]

    @property
    def split_quality(self):
        return self.__split_quality

    def classify(self, data):

        if self.split_quality == -float('inf'):
            raise ValueError("Split Quality should not be -inf!")

        if not isinstance(data, tuple):
            raise(TypeError, "data must be a tuple")

        group = data[self.cut_dim] <= self.cut_val

        return group == 0
