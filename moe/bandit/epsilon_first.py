# -*- coding: utf-8 -*-
"""Classes (Python) to compute the Bandit Epsilon-First arm allocation and choosing the arm to pull next.

See :class:`moe.bandit.epsilon.Epsilon` for further details on bandit.

"""
import numpy

from moe.bandit.constant import DEFAULT_EPSILON, DEFAULT_TOTAL_SAMPLES, EPSILON_SUBTYPE_FIRST
from moe.bandit.epsilon import Epsilon


class EpsilonFirst(Epsilon):

    r"""Implementation of EpsilonFirst.

    A class to encapsulate the computation of bandit epsilon first.

    total_samples is the total number of samples (#to sample + #sampled)
    #sampled is calculated by summing up total from each arm sampled.
    total_samples is T from :doc:`bandit`.

    See superclass :class:`moe.bandit.epsilon.Epsilon` for further details.

    """

    def __init__(
            self,
            historical_info,
            epsilon=DEFAULT_EPSILON,
            total_samples=DEFAULT_TOTAL_SAMPLES,
    ):
        """Construct an EpsilonFirst object. See superclass :class:`moe.bandit.epsilon.Epsilon` for details.

        total_samples is the total number of samples (#to sample + #sampled)
        #sampled is calculated by summing up total from each arm sampled.
        total_samples is T from :doc:`bandit`.

        """
        super(EpsilonFirst, self).__init__(
            historical_info=historical_info,
            subtype=EPSILON_SUBTYPE_FIRST,
            epsilon=epsilon,
            )
        self._total_samples = total_samples

    def allocate_arms(self):
        r"""Compute the allocation to each arm given ``historical_info``, running bandit ``subtype`` endpoint with hyperparameters in ``hyperparameter_info``.

        Computes the allocation to each arm based on the given subtype, historical info, and hyperparameter info.

        Works with k-armed bandits (k >= 1).

        The Algorithm: http://en.wikipedia.org/wiki/Multi-armed_bandit#Approximate_solutions

        This method starts with a pure exploration phase, followed by a pure exploitation phase.
        If we have a total of T trials, the first :math:`\epsilon` T trials, we only explore.
        After that, we only exploit (t = :math:`\epsilon` T, :math:`\epsilon` T + 1, ..., T).

        In other words, this method will pull a random arm in the exploration phase.
        Then this method will pull the optimal arm (best expected return) in the exploitation phase.

        In case of a tie in the exploitation phase, the method will split the probability 1 among the optimal arms.

        For example, if we have three arms, two arms (arm1 and arm2) with an average payoff of 0.5 ({win:10, losee:10, total:20})
        and a new arm (arm3, average payoff is 0 and total is 0).

        Let the epsilon :math:`\epsilon` be 0.1.

        The allocation depends on which phase we are in:

        Case 1: T = 50

        Recall that T = #to sample + #sampled. #sampled = 20 + 20 + 0 = 40.
        So we are on trial #41. We explore the first :math:`\epsilon T = 0.1 * 50 = 5` trials
        and thus we are in the exploitation phase. We split probability 1 between the optimal arms arm1 and arm2.

        arm1: 0.5, arm2: 0.5, arm3: 0.0.

        Case 2: T = 500

        We explore the first :math:`\epsilon T = 0.1 * 500 = 50` trials.
        Since we are on trail #41, we are in the exploration phase. We choose arms randomly:

        arm1: 0.33, arm2: 0.33, arm3: 0.33.

        :return: the dictionary of (arm, allocation) key-value pairs
        :rtype: a dictionary of (String(), float64) pairs
        """
        arms_sampled = self._historical_info.arms_sampled
        num_arms = self._historical_info.num_arms

        if not arms_sampled:
            raise ValueError('sample_arms are empty!')

        num_sampled = sum([sampled_arm.total for sampled_arm in arms_sampled.itervalues()])
        # Exploration phase, trials 1,2,..., epsilon * T
        # Allocate equal probability to all arms
        if num_sampled < self._total_samples * self._epsilon:
            equal_allocation = 1.0 / num_arms
            arms_to_allocations = {}
            for arm_name in arms_sampled.iterkeys():
                arms_to_allocations[arm_name] = equal_allocation
            return arms_to_allocations

        # Exploitation phase, trials 1,2,..., epsilon * T+1, ..., T
        avg_payoff_arm_name_list = []
        for arm_name, sampled_arm in arms_sampled.iteritems():
            avg_payoff = numpy.float64(sampled_arm.win - sampled_arm.loss) / sampled_arm.total if sampled_arm.total > 0 else 0
            avg_payoff_arm_name_list.append((avg_payoff, arm_name))
        avg_payoff_arm_name_list.sort(reverse=True)

        best_payoff, _ = avg_payoff_arm_name_list[0]
        # Filter out arms that have average payoff less than the best payoff
        winning_arm_payoff_name_list = filter(lambda avg_payoff_arm_name: avg_payoff_arm_name[0] == best_payoff, avg_payoff_arm_name_list)
        # Extract a list of winning arm names from a list of (average payoff, arm name) tuples.
        _, winning_arm_name_list = map(list, zip(*winning_arm_payoff_name_list))
        winning_arm_names = frozenset(winning_arm_name_list)

        num_winning_arms = len(winning_arm_names)
        arms_to_allocations = {}

        winning_arm_allocation = 1.0 / num_winning_arms
        # Split allocation among winning arms, all other arms get allocation of 0.
        for arm_name in arms_sampled.iterkeys():
            arms_to_allocations[arm_name] = winning_arm_allocation if arm_name in winning_arm_names else 0.0

        return arms_to_allocations
