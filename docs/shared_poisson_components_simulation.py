import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns



def simulate_karlis_ntzoufras(lam1, lam2, lam3, num_matches=10000):
    # Independent Poisson draws
    Z1 = np.random.poisson(lam1, num_matches)
    Z2 = np.random.poisson(lam2, num_matches)
    Z3 = np.random.poisson(lam3, num_matches) # The shared intensity

    # Actual goals
    X = Z1 + Z3 # Home goals
    Y = Z2 + Z3 # Away goals

    corr = np.corrcoef(X, Y)[0, 1]

    plt.figure(figsize=(8, 6))
    counts, xedges, yedges, im = plt.hist2d(X, Y, bins=(range(8), range(8)), cmap='Blues', density=True)

    for i in range(len(xedges)-1):
        for j in range(len(yedges)-1):
            if counts[i, j] > 0:
                plt.text(xedges[i]+0.5, yedges[j]+0.5, f"{counts[i,j]:.3f}",
                         color='black' if counts[i, j] < 0.05 else 'white',
                         ha='center', va='center', fontsize=8)

    plt.colorbar(label='Probability')
    plt.title(f'Bivariate Poisson model\n$\\lambda_1={lam1}, \\lambda_2={lam2}, \\lambda_3={lam3}$ (Corr: {corr:.2f})')
    plt.xlabel('Goals Team 1 (X)')
    plt.ylabel('Goals Team 2 (Y)')
    plt.xticks(np.arange(0.5, 7.5, 1), range(7))
    plt.yticks(np.arange(0.5, 7.5, 1), range(7))
    plt.show()

# No shared intensity, Z3 = 0
simulate_karlis_ntzoufras(lam1=1, lam2=1.5, lam3=0.0)

# High shared intensity, Z3 = 1.0
simulate_karlis_ntzoufras(lam1=1, lam2=1.5, lam3=2.0)
