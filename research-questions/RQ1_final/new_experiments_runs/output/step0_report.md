# Step 0 - validity: FAILED

Runs loaded: 544 of 544 planned (136 cells x 4 rounds). Data: `/home/silvia/Documents/GraduationProject/research-questions/RQ1_final/os-experiments/test-results/results`.

| check | rule | failing runs |
|---|---|---|
| a | 5000 jobs per run, 4 rounds per cell | 0 |
| b | median C / median C of full isolation (same placement, P, U, round): 0.97-1.03; frequency pinning removed: < 1 | 107 |
| c | full isolation: median C / (0.7 Q): 0.97-1.03 | 43 |

**A check failed. The analysis stops here (steps 1-5 and figures were not run).** Failing runs:

## Check b (107)

| run (placement, configuration, scale, U[, round]) | detail |
|---|---|
| single-core, isolcpus removed, tight, 0.5, 2 | ratio 0.9416, expected 0.97-1.03 |
| single-core, isolcpus removed, tight, 0.5, 3 | ratio 0.9666, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, tight, 0.1, 2 | ratio 0.9677, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, tight, 0.1, 3 | ratio 1.0319, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, tight, 0.5, 1 | ratio 0.9646, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, tight, 0.5, 2 | ratio 0.9667, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, tight, 0.7, 2 | ratio 0.9651, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, tight, 0.7, 4 | ratio 0.9661, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, soft, 0.1, 2 | ratio 0.9680, expected 0.97-1.03 |
| single-core, rcu_nocbs removed, soft, 0.7, 2 | ratio 0.9686, expected 0.97-1.03 |
| single-core, systemd containment removed, tight, 0.5, 3 | ratio 1.0365, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.1, 2 | ratio 0.9603, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.1, 3 | ratio 1.0303, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.5, 1 | ratio 0.9403, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.5, 2 | ratio 0.9682, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.7, 2 | ratio 0.9675, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.7, 4 | ratio 1.0325, expected 0.97-1.03 |
| single-core, IRQ steering removed, tight, 0.94, 1 | ratio 0.9660, expected 0.97-1.03 |
| single-core, IRQ steering removed, soft, 0.1, 3 | ratio 1.0316, expected 0.97-1.03 |
| single-core, IRQ steering removed, soft, 0.94, 3 | ratio 1.0421, expected 0.97-1.03 |
| single-core, frequency pinning removed, tight, 0.1, 3 | ratio 1.0228, expected < 1 |
| single-core, frequency pinning removed, tight, 0.1, 4 | ratio 1.0117, expected < 1 |
| single-core, frequency pinning removed, tight, 0.5, 3 | ratio 1.0083, expected < 1 |
| single-core, frequency pinning removed, tight, 0.5, 4 | ratio 1.0131, expected < 1 |
| single-core, frequency pinning removed, tight, 0.7, 3 | ratio 1.0159, expected < 1 |
| single-core, frequency pinning removed, tight, 0.7, 4 | ratio 1.0177, expected < 1 |
| single-core, frequency pinning removed, tight, 0.94, 3 | ratio 1.0175, expected < 1 |
| single-core, frequency pinning removed, tight, 0.94, 4 | ratio 1.0162, expected < 1 |
| single-core, frequency pinning removed, soft, 0.1, 3 | ratio 1.0067, expected < 1 |
| single-core, frequency pinning removed, soft, 0.1, 4 | ratio 1.0135, expected < 1 |
| single-core, frequency pinning removed, soft, 0.5, 3 | ratio 1.0189, expected < 1 |
| single-core, frequency pinning removed, soft, 0.5, 4 | ratio 1.0184, expected < 1 |
| single-core, frequency pinning removed, soft, 0.7, 3 | ratio 1.0112, expected < 1 |
| single-core, frequency pinning removed, soft, 0.7, 4 | ratio 1.0042, expected < 1 |
| single-core, frequency pinning removed, soft, 0.94, 3 | ratio 1.0208, expected < 1 |
| single-core, frequency pinning removed, soft, 0.94, 4 | ratio 1.0000, expected < 1 |
| single-core, boot-params bundle removed, tight, 0.1, 2 | ratio 0.9673, expected 0.97-1.03 |
| single-core, boot-params bundle removed, tight, 0.7, 1 | ratio 0.9574, expected 0.97-1.03 |
| single-core, boot-params bundle removed, tight, 0.94, 1 | ratio 0.9684, expected 0.97-1.03 |
| single-core, all defaults, tight, 0.5, 2 | ratio 0.9517, expected 0.97-1.03 |
| single-core, all defaults, tight, 0.7, 2 | ratio 0.9544, expected 0.97-1.03 |
| single-core, all defaults, soft, 0.7, 3 | ratio 1.0361, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.1, 3 | ratio 0.9500, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.1, 4 | ratio 0.9440, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.5, 1 | ratio 0.9489, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.5, 4 | ratio 0.9693, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.7, 1 | ratio 1.0402, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.7, 3 | ratio 0.9446, expected 0.97-1.03 |
| multi-core, isolcpus removed, tight, 0.7, 4 | ratio 0.9629, expected 0.97-1.03 |
| multi-core, nohz_full removed, tight, 0.1, 3 | ratio 1.0303, expected 0.97-1.03 |
| multi-core, nohz_full removed, tight, 0.7, 2 | ratio 0.9558, expected 0.97-1.03 |
| multi-core, nohz_full removed, tight, 0.94, 1 | ratio 0.9463, expected 0.97-1.03 |
| multi-core, nohz_full removed, soft, 0.1, 4 | ratio 1.0304, expected 0.97-1.03 |
| multi-core, nohz_full removed, soft, 0.5, 3 | ratio 1.0481, expected 0.97-1.03 |
| multi-core, nohz_full removed, soft, 0.5, 4 | ratio 1.0514, expected 0.97-1.03 |
| multi-core, nohz_full removed, soft, 0.7, 3 | ratio 1.0371, expected 0.97-1.03 |
| multi-core, nohz_full removed, soft, 0.94, 2 | ratio 0.9519, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, tight, 0.1, 2 | ratio 0.9609, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, tight, 0.5, 4 | ratio 0.9627, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, tight, 0.7, 4 | ratio 0.9685, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, soft, 0.1, 3 | ratio 1.0353, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, soft, 0.5, 2 | ratio 0.9665, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, soft, 0.7, 2 | ratio 0.9690, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, soft, 0.94, 2 | ratio 0.9692, expected 0.97-1.03 |
| multi-core, rcu_nocbs removed, soft, 0.94, 4 | ratio 0.9566, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.5, 2 | ratio 0.9611, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.5, 3 | ratio 0.9492, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.5, 4 | ratio 0.9680, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.7, 1 | ratio 1.0433, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.7, 2 | ratio 0.9627, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.7, 4 | ratio 0.9693, expected 0.97-1.03 |
| multi-core, systemd containment removed, tight, 0.94, 4 | ratio 0.9628, expected 0.97-1.03 |
| multi-core, systemd containment removed, soft, 0.7, 1 | ratio 1.0528, expected 0.97-1.03 |
| multi-core, systemd containment removed, soft, 0.94, 2 | ratio 0.9615, expected 0.97-1.03 |
| multi-core, systemd containment removed, soft, 0.94, 4 | ratio 0.9690, expected 0.97-1.03 |
| multi-core, IRQ steering removed, tight, 0.1, 3 | ratio 1.0403, expected 0.97-1.03 |
| multi-core, IRQ steering removed, tight, 0.5, 1 | ratio 0.9623, expected 0.97-1.03 |
| multi-core, IRQ steering removed, tight, 0.5, 3 | ratio 1.0414, expected 0.97-1.03 |
| multi-core, IRQ steering removed, tight, 0.7, 3 | ratio 1.0327, expected 0.97-1.03 |
| multi-core, IRQ steering removed, tight, 0.94, 1 | ratio 0.9659, expected 0.97-1.03 |
| multi-core, IRQ steering removed, soft, 0.1, 2 | ratio 0.9682, expected 0.97-1.03 |
| multi-core, IRQ steering removed, soft, 0.1, 3 | ratio 1.0346, expected 0.97-1.03 |
| multi-core, IRQ steering removed, soft, 0.5, 2 | ratio 0.9676, expected 0.97-1.03 |
| multi-core, IRQ steering removed, soft, 0.94, 2 | ratio 0.9590, expected 0.97-1.03 |
| multi-core, IRQ steering removed, soft, 0.94, 3 | ratio 1.0381, expected 0.97-1.03 |
| multi-core, frequency pinning removed, tight, 0.1, 1 | ratio 1.0107, expected < 1 |
| multi-core, frequency pinning removed, tight, 0.1, 3 | ratio 1.0458, expected < 1 |
| multi-core, frequency pinning removed, tight, 0.5, 3 | ratio 1.0184, expected < 1 |
| multi-core, frequency pinning removed, tight, 0.7, 1 | ratio 1.0407, expected < 1 |
| multi-core, frequency pinning removed, tight, 0.7, 3 | ratio 1.0165, expected < 1 |
| multi-core, frequency pinning removed, tight, 0.94, 1 | ratio 1.0040, expected < 1 |
| multi-core, frequency pinning removed, tight, 0.94, 3 | ratio 1.0106, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.1, 3 | ratio 1.0311, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.1, 4 | ratio 1.0047, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.5, 1 | ratio 1.0030, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.5, 3 | ratio 1.0218, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.5, 4 | ratio 1.0129, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.7, 3 | ratio 1.0154, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.7, 4 | ratio 1.0033, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.94, 1 | ratio 1.0029, expected < 1 |
| multi-core, frequency pinning removed, soft, 0.94, 3 | ratio 1.0349, expected < 1 |
| multi-core, boot-params bundle removed, tight, 0.5, 1 | ratio 0.9260, expected 0.97-1.03 |
| multi-core, boot-params bundle removed, tight, 0.7, 1 | ratio 1.0415, expected 0.97-1.03 |
| multi-core, boot-params bundle removed, tight, 0.94, 4 | ratio 0.9415, expected 0.97-1.03 |
| multi-core, boot-params bundle removed, soft, 0.94, 2 | ratio 0.9625, expected 0.97-1.03 |
| multi-core, all defaults, tight, 0.5, 2 | ratio 0.9672, expected 0.97-1.03 |
| multi-core, all defaults, tight, 0.7, 4 | ratio 0.9692, expected 0.97-1.03 |

## Check c (43)

| run (placement, configuration, scale, U[, round]) | detail |
|---|---|
| single-core, full isolation, tight, 0.1, 2 | median C / (0.7 Q) = 1.0408, expected 0.97-1.03 |
| single-core, full isolation, tight, 0.5, 1 | median C / (0.7 Q) = 1.0350, expected 0.97-1.03 |
| single-core, full isolation, tight, 0.5, 2 | median C / (0.7 Q) = 1.0347, expected 0.97-1.03 |
| single-core, full isolation, tight, 0.7, 1 | median C / (0.7 Q) = 1.0357, expected 0.97-1.03 |
| single-core, full isolation, tight, 0.7, 2 | median C / (0.7 Q) = 1.0370, expected 0.97-1.03 |
| single-core, full isolation, tight, 0.94, 1 | median C / (0.7 Q) = 1.0363, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.1, 1 | median C / (0.7 Q) = 1.1903, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.1, 2 | median C / (0.7 Q) = 1.1911, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.1, 3 | median C / (0.7 Q) = 1.1532, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.1, 4 | median C / (0.7 Q) = 1.1728, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.5, 1 | median C / (0.7 Q) = 1.0659, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.5, 2 | median C / (0.7 Q) = 1.0602, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.5, 3 | median C / (0.7 Q) = 1.0364, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.5, 4 | median C / (0.7 Q) = 1.0509, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.7, 1 | median C / (0.7 Q) = 1.0562, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.7, 2 | median C / (0.7 Q) = 1.0578, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.7, 4 | median C / (0.7 Q) = 1.0382, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.94, 1 | median C / (0.7 Q) = 1.0367, expected 0.97-1.03 |
| single-core, full isolation, soft, 0.94, 2 | median C / (0.7 Q) = 1.0415, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.1, 1 | median C / (0.7 Q) = 1.0302, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.1, 2 | median C / (0.7 Q) = 1.0434, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.1, 4 | median C / (0.7 Q) = 1.0339, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.5, 1 | median C / (0.7 Q) = 1.0368, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.5, 2 | median C / (0.7 Q) = 1.0387, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.5, 4 | median C / (0.7 Q) = 1.0348, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.7, 2 | median C / (0.7 Q) = 1.0316, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.7, 4 | median C / (0.7 Q) = 1.0325, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.94, 1 | median C / (0.7 Q) = 1.0365, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.94, 2 | median C / (0.7 Q) = 1.0385, expected 0.97-1.03 |
| multi-core, full isolation, tight, 0.94, 4 | median C / (0.7 Q) = 1.0365, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.1, 1 | median C / (0.7 Q) = 1.1930, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.1, 2 | median C / (0.7 Q) = 1.1955, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.1, 3 | median C / (0.7 Q) = 1.1518, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.1, 4 | median C / (0.7 Q) = 1.1757, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.5, 1 | median C / (0.7 Q) = 1.0616, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.5, 2 | median C / (0.7 Q) = 1.0669, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.5, 4 | median C / (0.7 Q) = 1.0397, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.7, 1 | median C / (0.7 Q) = 1.0562, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.7, 2 | median C / (0.7 Q) = 1.0578, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.7, 4 | median C / (0.7 Q) = 1.0387, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.94, 1 | median C / (0.7 Q) = 1.0368, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.94, 2 | median C / (0.7 Q) = 1.0814, expected 0.97-1.03 |
| multi-core, full isolation, soft, 0.94, 4 | median C / (0.7 Q) = 1.0477, expected 0.97-1.03 |

## Summary of the ratios (all runs loaded)

- median C / full isolation, all configurations except frequency pinning removed: min 0.9260, max 1.0528
- median C / full isolation, frequency pinning removed: min 0.9365, max 1.0458
- full isolation median C / (0.7 Q): min 0.9936, max 1.1955

