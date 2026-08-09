import numpy as np

a = 4.27
lat = np.eye(3) * a

fracs = np.array([
    [0.00, 0.00, 0.00],  # O1
    [0.50, 0.50, 0.50],  # O2
    [0.25, 0.25, 0.25],  # Cu1
    [0.25, 0.75, 0.75],  # Cu2
    [0.75, 0.25, 0.75],  # Cu3
    [0.75, 0.75, 0.25],  # Cu4
])
labels = ['O1','O2','Cu1','Cu2','Cu3','Cu4']
cart = fracs @ lat

def min_dist(p1, p2):
    best = 1e9
    for i in [-1,0,1]:
        for j in [-1,0,1]:
            for k in [-1,0,1]:
                shift = i*lat[0]+j*lat[1]+k*lat[2]
                d = float(np.linalg.norm(p1-p2+shift))
                if d > 1e-6:
                    best = min(best, d)
    return best

theory = np.sqrt(3)/4*a
print(f'Theory Cu-O nearest: sqrt(3)/4*a = {theory:.4f} Ang')

for i, (li, ci) in enumerate(zip(labels, cart)):
    dists = []
    for j, (lj, cj) in enumerate(zip(labels, cart)):
        if i==j: continue
        d = min_dist(ci, cj)
        dists.append((d, lj))
    dists.sort()
    print(f'{li}: nearest={dists[0][1]} d={dists[0][0]:.4f} | next={dists[1][1]} d={dists[1][0]:.4f}')

print()
print('Cu O-coordination (# O within 2.1 Ang):')
for i in range(2,6):
    cnt = sum(1 for j in range(2) if min_dist(cart[i], cart[j]) < 2.1)
    print(f'  {labels[i]}: {cnt} O neighbors')

print('O Cu-coordination (# Cu within 2.1 Ang):')
for i in range(2):
    cnt = sum(1 for j in range(2,6) if min_dist(cart[i], cart[j]) < 2.1)
    print(f'  {labels[i]}: {cnt} Cu neighbors')

# Symmetry check: all Cu-Cu and Cu-O distances
print('\nAll Cu-Cu distances:')
for i in range(2,6):
    for j in range(i+1,6):
        print(f'  {labels[i]}-{labels[j]}: {min_dist(cart[i], cart[j]):.4f}')
