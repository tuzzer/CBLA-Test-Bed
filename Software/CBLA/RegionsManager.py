__author__ = 'Matthew'

import math
import random
from copy import copy
from sklearn import linear_model

class Expert():

    max_training_data_num = 2000

    def __init__(self):

        # child expert
        self.left = None
        self.right = None

        # region splitter
        self.region_splitter = None

        # memory
        self.training_data = []
        self.training_label = []

        # prediction model
        self.predict_model = linear_model.LinearRegression()

        # error is max at first
        self.mean_error = float("inf")

        # knowledge gain assessor
        self.kga = KGA(self.mean_error)

        # histroical reward history
        self.rewards_history = [0]

    def append(self, SM, S1, S1_predicted=None):

        if not isinstance(SM, tuple):
            raise(TypeError, "SM must be a tuple")
        if not isinstance(S1, tuple):
            raise(TypeError, "S1 must be a tuple")
        if S1_predicted is not None and not isinstance(S1_predicted, tuple):
            raise(TypeError, "S1_predicted must be a tuple")

        if self.left is None and self.right is None:
            self.training_data.append(SM)
            self.training_label.append(S1)

            if len(self.training_data) > Expert.max_training_data_num:
                self.training_data.pop(0)
                self.training_label.pop(0)

            # update prediction model
            self.train()

            # update the KGA
            if S1_predicted is not None:
                self.kga.append_error(S1, S1_predicted)
                self.mean_error = self.kga.calc_mean_error()  # used to determine if splitting is necessary
                self.rewards_history.append(self.kga.calc_reward())
                self.rewards_history = self.rewards_history[-1:]

        # Cases when only one of the child is NONE
        elif self.left is None or self.right is None:
            raise(Exception, "Expert's Tree structure is corrupted! One child branch is missing")

        # delegate to child nodes
        elif self.region_splitter.classify(SM):
            self.right.append(SM, S1, S1_predicted)
        else:
            self.left.append(SM, S1, S1_predicted)

    def train(self):
        try:
            self.predict_model.fit(self.training_data, self.training_label)
        except ValueError:
            pass

    def predict(self, S, M):

        if not isinstance(S, tuple):
            raise(TypeError, "S must be a tuple")
        if not isinstance(M, tuple):
            raise(TypeError, "M must be a tuple")

        # this is leaf node
        if self.left is None and self.right is None:
            try:
                S1 = tuple(self.predict_model.predict(S+M))
            except AttributeError:
                S1 = S
            return S1

        # Cases when only one of the child is NONE
        elif self.left is None or self.right is None:
            raise(Exception, "Expert's Tree structure is corrupted! One child branch is missing")

        # delegate to child nodes
        if self.region_splitter.classify(S+M):
            return self.right.predict(S,M)
        else:
            return self.left.predict(S,M)

    def is_splitting(self):
        split_threshold = 500
        mean_error_threshold = 100
        if len(self.training_data) > split_threshold and self.mean_error > mean_error_threshold:
            return True
        return False

    def split(self):

        # this is leaf node
        if self.left is None and self.right is None:

            if self.is_splitting():
                print("It's splitting")
                # instantiate the splitter
                self.region_splitter = RegionSplitter(self.training_data, self.training_label)

                # instantiate the left and right expert
                self.right = Expert()
                self.left = Expert()

                # split the data to the correct region
                for i in range(len(self.training_data)):
                    if self.region_splitter.classify(self.training_data[i]):
                        self.right.append(self.training_data[i], self.training_label[i])
                    else:
                        self.left.append(self.training_data[i], self.training_label[i])

                # if either of them is empty
                if len(self.left.training_data) == 0 or len(self.right.training_data) == 0:
                    # do not split
                    self.right = None
                    self.left = None
                    self.region_splitter = None
                    return

                # transferring "knowledge" to child nodes
                self.right.mean_error = self.mean_error
                self.right.rewards_history = copy(self.rewards_history)
                self.right.kga.errors = copy(self.kga.errors)
                self.left.mean_error = self.mean_error
                self.left.rewards_history = copy(self.rewards_history)
                self.left.kga.errors = copy(self.kga.errors)

                # clear the training data at the parent node so they don't get modified accidentally
                self.training_data = []
                self.training_label = []
                # clear everything as they are not needed any more
                self.mean_error = None
                self.predict_model = None
                self.kga = None
                self.rewards_history = None

        # Cases when only one of the child is NONE
        elif self.left is None and self.right is None:
            raise(Exception, "Expert's Tree structure is corrupted! One child branch is missing")

        else:
            # delegate to child nodes
            self.right.split()
            self.left.split()

    def get_next_action(self, S1):

        if not isinstance(S1, tuple):
            raise(TypeError, "S1 must be a tuple")

        # this is leaf node
        if self.left is None and self.right is None:
            #print("Mean Error", self.mean_error)

            if len(self.training_data) == 0:
                raise(Exception, "This node has no training data!")

            if self.is_possible(S1):
                # reward is just the reward in the most recent time region
                expected_reward = self.rewards_history[-1]
            else:
                expected_reward = -float("inf")

            # find out the indices of M data
            M_index = (len(self.training_data[0]) - len(S1), len(self.training_data[0]))

            # extract the M part of the data out
            M1 = zip(*self.training_data)
            M1 = tuple(M1)[M_index[0]:M_index[1]]

            # take the average of the M1 in each dimension
            M1 = tuple([sum(M1[i])/len(M1[i]) for i in range(len(M1))])


            return (M1, expected_reward)

        # Cases when only one of the child is NONE
        elif self.left is None and self.right is None:
            raise(Exception, "Expert's Tree structure is corrupted! One child branch is missing")

        else:


            # return the child node with the largest reward
            next_action_L = self.left.get_next_action(S1)
            next_action_R = self.right.get_next_action(S1)

            if next_action_L[1] > next_action_R[1]:
                return next_action_L
            else:
                return next_action_R

    def is_possible(self, S1):

        # check if the S1 is within the min and max range of all existing data points
        data_transpose = list(zip(*self.training_data))
        for i in range(len(S1)):
            min_S = min(data_transpose[i])
            max_S = max(data_transpose[i])
            if min_S > S1[i] or max_S < S1[i]:
                return False
        return True

    def print(self, level=0):

        # this is leaf node
        if self.left is None and self.right is None:
            mean_error_string = '%.*f' % (2, self.mean_error)
            print(len(self.training_data), "(err =", mean_error_string, ") --", self.training_data)

        else:
            print(" L ** ", end="")
            self.left.print(level+1)
            print("      " * level, "R ** ", end="")
            self.right.print(level+1)

class RegionSplitter():

    def __init__(self, data, label):

        self.cut_dim = 0
        self.cut_val = 0

        # TODO: need proper clustering

        sample_num = len(data)
        dim_num = len(data[0])

        # combine the data and the label for sorting purposes
        exemplars = [(data[i], label[i]) for i in range(sample_num)]

        # sort in each dimension
        dim_max_range = 0
        for i in range(dim_num):
            exemplars.sort(key=lambda exemplar: exemplar[0][i])

            if dim_max_range < exemplars[-1][0][i] - exemplars[0][0][i]:
                self.cut_dim = i

        self.cut_val = exemplars[int(sample_num/2)][0][self.cut_dim]

    def classify(self, data):
        if not isinstance(data, tuple):
            raise(TypeError, "data must be a tuple")

        return data[self.cut_dim] > self.cut_val


class KGA():

    def __init__(self, e0):
        if not isinstance(e0, float):
            raise(TypeError, "e0 must be a float")
        self.errors = [e0]

        # smoothing parameter
        self.delta = 5.0

        # time window
        self.tau = 4.0

    def append_error(self, S_actual, S_predicted):
        if not isinstance(S_actual, tuple):
            raise(TypeError, "S_actual must be a tuple")
        if not isinstance(S_predicted, tuple):
            raise(TypeError, "S_predicted must be a tuple")

        error = 0
        for i in range(len(S_actual)):
            error += (S_actual[i] - S_predicted[i])**2

        print("Prediction Error: ", error)
        self.errors.append(error)

    def calc_mean_error(self):

        # if there aren't enough error in the history yet
        if len(self.errors) == 0:
            mean_error = float("inf")
        else:
            mean_error = math.fsum(self.errors[-int(self.delta):])/self.delta
        return mean_error

    def metaM(self):

        # if there aren't enough error in the history yet
        if len(self.errors) == 0:
            mean_error_predicted = float("inf")
        elif len(self.errors) < self.delta:
            mean_error_predicted = self.errors[0]
        else:
            mean_error_predicted = math.fsum(self.errors[-int(self.delta+self.tau):-int(self.tau)])/self.delta
        return mean_error_predicted

    def calc_reward(self):
        #remove old histories that are not needed
        self.errors = self.errors[-int(self.delta+self.tau):]
        reward = self.metaM() - self.calc_mean_error()
        if math.isnan(reward): # happens when it's inf - inf
            reward = 0
        return reward


if __name__ == "__main__":

    # generating exemplars
    exemplars = []
    for i in range(1,15):
        exemplar = ((math.floor(100*math.sin(math.pi*i/4)),),
                    (math.floor(100*math.sin(math.pi*i/3)),),
                    (math.floor(100*math.sin(math.pi*i/2)),))
        exemplars.append(exemplar)
    print("Generated exemplars: ", exemplars)

    # instantiate an Expert
    expert = Expert()

    # appending data to expert
    for exemplar in exemplars:

        S = exemplar[0]
        M = exemplar[1]
        S1 = exemplar[2]
        print("\n Test case ", S, M, S1)

        # have the expert make prediction
        S1_predicted = expert.predict(S, M)
        print(S1_predicted)

        # do action


        # add exemplar to expert
        expert.append(S + M, S1, S1_predicted)
        expert.split()  # won't actually split if the condition is not met

        M1, L = expert.get_next_action(S1)
        print("Expected Reward", L)
        print("Next Action", M1)

    expert.print()