import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import nbinom

def frank_copula(u, v, theta):
    """Computes the bivariate Frank Copula CDF."""
    if abs(theta) < 1e-6:
        return u * v
    num = (np.exp(-theta * u) - 1) * (np.exp(-theta * v) - 1)
    den = np.exp(-theta) - 1
    return -1.0 / theta * np.log(1 + num / den)

def compute_discrete_copula_matrix(mu_x, alpha_x, mu_y, alpha_y, theta, max_goals=6):
    """
    Generates a joint probability matrix using Negative Binomial marginals 
    and a Frank Copula via finite cell differentiation.
    """
    n_x = 1.0 / alpha_x
    p_x = 1.0 / (alpha_x * mu_x + 1.0)
    
    n_y = 1.0 / alpha_y
    p_y = 1.0 / (alpha_y * mu_y + 1.0)
    
    matrix = np.zeros((max_goals + 1, max_goals + 1))

    F_X = [nbinom.cdf(x, n_x, p_x) for x in range(-1, max_goals + 1)]
    F_Y = [nbinom.cdf(y, n_y, p_y) for y in range(-1, max_goals + 1)]
    
    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            u_x = F_X[x + 1]
            u_xm1 = F_X[x]
            v_y = F_Y[y + 1]
            v_ym1 = F_Y[y]
            
            c_00 = frank_copula(u_x, v_y, theta)
            c_10 = frank_copula(u_xm1, v_y, theta)
            c_01 = frank_copula(u_x, v_ym1, theta)
            c_11 = frank_copula(u_xm1, v_ym1, theta)
            
            matrix[y, x] = c_00 - c_10 - c_01 + c_11
            
    return matrix

def calculate_correlation(matrix):
    """Calculates exact Pearson correlation from the discrete joint probability matrix."""
    max_goals = matrix.shape[0] - 1
    x_indices = np.arange(max_goals + 1)
    y_indices = np.arange(max_goals + 1)
    
    px = np.sum(matrix, axis=0)
    py = np.sum(matrix, axis=1)
    
    ex = np.sum(x_indices * px)
    ey = np.sum(y_indices * py)
    
    var_x = np.sum((x_indices ** 2) * px) - ex ** 2
    var_y = np.sum((y_indices ** 2) * py) - ey ** 2
    
    exy = 0
    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            exy += x * y * matrix[y, x]
            
    cov = exy - (ex * ey)
    if var_x > 0 and var_y > 0:
        return cov / np.sqrt(var_x * var_y)
    return 0.0

# Execution
mu_team1, alpha_team1 = 1.5, 0.4
mu_team2, alpha_team2 = 1.2, 0.4
theta_dependence = -2.0

prob_matrix = compute_discrete_copula_matrix(mu_team1, alpha_team1, mu_team2, alpha_team2, theta_dependence)
corr = calculate_correlation(prob_matrix)

plt.figure(figsize=(8, 6))
plt.imshow(prob_matrix, origin='lower', cmap='Blues', aspect='equal')

for x in range(prob_matrix.shape[1]):
    for y in range(prob_matrix.shape[0]):
        plt.text(x, y, f"{prob_matrix[y, x]:.3f}", ha='center', va='center',
                 color='black' if prob_matrix[y, x] < 0.04 else 'white', fontsize=9)

plt.colorbar(label='Probability')
plt.xlabel('Goals Team 1 (X)')
plt.ylabel('Goals Team 2 (Y)')

title_str = (f"Discrete Frank Copula with NB Margins\n"
             f"$\\mu_1={mu_team1}, \\alpha_1={alpha_team1}, \\mu_2={mu_team2}, \\alpha_2={alpha_team2}, \\theta={theta_dependence}$ "
             f"(Corr: {corr:.2f})")
plt.title(title_str)

plt.tight_layout()
plt.savefig('Figure_3.pdf', format='pdf')
plt.close()