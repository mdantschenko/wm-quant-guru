"""Layer 3 of the concept: from a distribution to an action.

DecisionStrategy is the abstract base. Mode A sizes a bet with fractional
Kelly, mode B picks the tip that scores best under the rules of the round.
Both read the same matrix, only the goal function differs.
"""
