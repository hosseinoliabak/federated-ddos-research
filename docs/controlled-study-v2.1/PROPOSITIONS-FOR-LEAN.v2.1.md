# Propositions for the Lean check (design v2.1)

Status: statements only, written for Root to formalise. The design worker wrote no Lean and did not touch the formal-verification tree. Each item says what the design cites it for and carries one of three classes.

- **[E] elementary fact.** A general statement with a short proof. These are the candidates for Lean.
- **[N] numeric result only.** A value that holds for the stated planning numbers. It comes from an exact sum of probability mass functions or from the seeded simulation in `v2.1-computation/`. It is not a theorem, although a few can be certified by finite rational arithmetic, as noted.
- **[S] already machine-checked.** Cited FROM-SOURCE, unchanged.

The classes map onto the labels used in the design. Every [N] value is DERIVED, and [S] is FROM-SOURCE. The planning inputs behind the [N] values (benign mean 40, dispersion 0.2, selection probability 1/4, 60 plateau windows, correlation 0.05, margin 0.05) are FROM-SOURCE or PROPOSED, as labelled in `DESIGN.v2.1.md`.

The idealization behind P1 to P6 is the one stated in v2: the keyed 1-in-4 selector keeps each eligible packet independently with probability p = 1/4. This treats the keyed hash as a random function. It is an assumption, not a proved property of the selector.

Notation. N is the number of eligible packets toward one destination in one one-second bin. S is the number of them selected. Given N = n, S is Binomial(n, p). The rescaled count is S/p, which is 4S at p = 1/4. NB(k, μ) is the negative binomial law with size k > 0 and mean μ > 0, with P(N = n) = Γ(k + n) / (n! Γ(k)) · (k/(k + μ))^k · (μ/(k + μ))^n for n = 0, 1, 2, …. Its variance is μ + μ²/k, so the dispersion φ of the design equals 1/k.

---

## P1. The rescaled count is unbiased [E]

**Statement.** Let N be a random variable with values in the nonnegative integers and finite mean, and let S given N = n be Binomial(n, p) with 0 < p ≤ 1. Then E[S/p | N] = N, and therefore E[S/p] = E[N]. At p = 1/4, E[4S] = E[N].

**Weighted form.** Let w_1, …, w_n be fixed nonnegative reals and I_1, …, I_n independent Bernoulli(p) variables. Then E[(1/p) Σ w_i I_i] = Σ w_i.

**Cited for.** Packets ×4 (all w_i = 1), bytes ×4 (w_i is the packet size), and SYN ×4 (w_i is 1 for a SYN packet and 0 otherwise) are unbiased. Unequal packet sizes do not bias the byte estimator.

**Proof idea.** Linearity of expectation with E[I_i] = p.

## P2. Conditional variance and coefficient of variation [E]

**Statement.** Under P1, Var(S/p | N = n) = n(1 − p)/p. At p = 1/4 this is 3n, so for n > 0 the coefficient of variation of 4S given N = n is √(3/n). Hence n ≥ 300 gives at most 0.1 and n ≥ 1,200 gives at most 0.05.

**Weighted form.** With 0 ≤ w_i ≤ b_max, Var((1/p) Σ w_i I_i) = ((1 − p)/p) Σ w_i² ≤ ((1 − p)/p) · b_max · Σ w_i. At p = 1/4 the bound is 3 · b_max · Σ w_i. With b_avg = (Σ w_i)/n, the coefficient of variation of the byte estimator is at most √(3/n) · √(b_max/b_avg).

**Cited for.** The relative standard error of a rescaled count, and the statement that packet-size spread enlarges the variance of the byte estimator, not its bias.

**Proof idea.** Var(I_i) = p(1 − p), independence, and w_i² ≤ b_max · w_i.

## P3. Variance of the rescaled count when the count itself is random [E]

**Statement.** If in addition E[N²] is finite, then Var(S/p) = Var(N) + ((1 − p)/p) · E[N]. At p = 1/4, Var(4S) = Var(N) + 3 · E[N].

**Corollary.** If Var(N) = μ + φμ² with E[N] = μ, then Var(4S) = 4μ + φμ².

**Cited for.** The benign rescaled count is more variable under pS than under p0. This is the source of the recall drop where the benign and attack-bin distributions overlap.

**Proof idea.** Law of total variance with P1 and P2: Var(S/p) = E[Var(S/p | N)] + Var(E[S/p | N]).

**Numbers [N].** μ = 40 and φ = 0.2 give Var(N) = 360 and Var(4S) = 480.

## P4. A thinned negative binomial is negative binomial with the same size [E]

**Statement.** If N is NB(k, μ) and S given N = n is Binomial(n, p), then S is NB(k, pμ).

**Cited for.** The exact law of the benign sampled count. With k = 5 and μ = 40 the benign count under p0 is NB(5, 40) and the benign sampled count under pS is NB(5, 10). The pS threshold is computed from the second law.

**Proof idea.** The probability generating function of NB(k, μ) is G(z) = (1 + (μ/k)(1 − z))^(−k). Thinning replaces z by 1 − p + pz, which gives (1 + (pμ/k)(1 − z))^(−k). A direct proof sums the product of the two mass functions over n.

**Integer size.** For integer k the mass function is C(n + k − 1, k − 1) · q^k · (1 − q)^n with q = k/(k + μ). Here q = 1/9 for mean 40 and q = 1/3 for mean 10.

**Numeric confirmation [N].** The script sums the thinned mass function and compares it with NB(5, 10). The largest absolute difference over s < 400 is 1.7 × 10⁻¹⁶.

## P5. A thinned Poisson is Poisson, and the two selected parts are independent [E]

**Statement.** If A is Poisson(λ) and S_A given A = a is Binomial(a, p), then S_A is Poisson(pλ). If B and A are independent counts whose packets are selected independently, the number selected from the B + A packets equals S_B + S_A, where S_B given B is Binomial(B, p), S_A given A is Binomial(A, p), and S_B and S_A are independent.

**Cited for.** The sampled count of an attack bin is the sum of an NB(5, 10) variable and an independent Poisson(10r) variable, where r is the intensity ratio.

## P6. Distinct source hosts under selection [E]

**Statement (a).** A host that sends k ≥ 1 packets in the bin has none selected with probability (1 − p)^k. At p = 1/4 this is (3/4)^k.

**Statement (b).** Let k_s ≥ 0 be the packet count of host s. The expected number of distinct hosts seen after selection is Σ_s (1 − (1 − p)^(k_s)). It is at most the true number of hosts with k_s ≥ 1, and strictly smaller when p < 1 and at least one host has k_s ≥ 1.

**Statement (c).** For 0 < p < 1, no constant factor corrects the count. (Root amendment after the Lean check: at p = 1 the constant c = 1 is exact, theorem `p6c_constant_at_one`; the design uses p = 1/4.) There is no real c with c · Σ_s (1 − (1 − p)^(k_s)) = #{s : k_s ≥ 1} for every configuration (k_s). At p = 1/4, n hosts with one packet each need c = 4, and n hosts with two packets each need c = 16/7.

**Statement (d).** If each of n sources emits an independent Poisson(Λ/n) number of packets in the bin, the expected number of distinct sources is n(1 − e^(−Λ/n)) before selection and n(1 − e^(−pΛ/n)) after it. If the benign sources and the bots are disjoint sets, the distinct count of the bin is the sum of the two parts.

**Cited for.** Distinct source hosts are not rescalable, and the design predicts them from the bin total, that is, concurrent benign occupancy plus attack occupancy.

## P7. The rank-rule threshold [E]

**Statement (a).** Let x_1, …, x_n be real scores, r = ⌈0.99 n⌉, and t the r-th smallest score. Then the number of i with x_i > t is at most n − r, which is at most n/100.

**Statement (b).** If X_1, …, X_(n+1) are exchangeable and almost surely distinct, then P(X_(n+1) > t) = (n − r + 1)/(n + 1), where t is the r-th smallest of X_1, …, X_n. With ties and the strict rule the probability is at most this value.

**Cited for.** The strict rule (alert only if score > threshold) keeps the false-positive fraction on the calibration pool at or below 1%. The expected false-positive rate on new benign windows is slightly above 1%.

**Numbers [N].** n = 1,200 gives r = 1,188, so the threshold is the 13th largest score and the value in (b) is 13/1,201 = 1.08%. n = 400 gives the 5th largest and 5/401 = 1.25%. n = 300 gives the 4th largest and 4/301 = 1.33%.

**Limit.** Exchangeability fails when windows inside a calibration episode are dependent. The simulation covers that case numerically.

## P8. Mean and variance of the paired alert difference [E]

**Statement.** Let X and Y take values in {0, 1} on one probability space, D = X − Y, p10 = P(X = 1, Y = 0), and p01 = P(X = 0, Y = 1). Then E[D] = P(X = 1) − P(Y = 1) = p10 − p01 and Var(D) = p10 + p01 − (p10 − p01)².

**Cited for.** X is the p0 alert and Y the pS alert of the same attack window. E[D] is the paired recall drop, and Var(D) is the per-window variance used in the planning arithmetic.

## P9. Design effect of a cluster mean [E]

**Statement (a).** Let D_1, …, D_m have a common variance σ² and a common correlation ρ between every pair. Then Var((1/m) Σ D_i) = (σ²/m) · (1 + (m − 1)ρ).

**Statement (b).** If D_1, …, D_m are independent and identically distributed given a variable U, then Cov(D_i, D_j) = Var(E[D_1 | U]) for i ≠ j, so ρ = Var(E[D_1 | U]) / Var(D_1).

**Cited for.** The episode is the cluster and its 60 plateau windows are the D_i. The factor 1 + (m − 1)ρ is the design effect. Statement (b) gives the correlation implied by an episode-level component of the benign rate.

**Numbers [N].** m = 60 and ρ = 0.05 give a design effect of 3.95.

## P10. An additive gamma split keeps the negative-binomial margin [E]

**Statement.** Let U be Gamma(a, θ) and V be Gamma(k − a, θ), independent, with 0 < a < k, shape first and scale second. Then U + V is Gamma(k, θ). If N given Λ is Poisson(Λ) and Λ is Gamma(k, θ), then N is NB(k, kθ). If two counts N_1 and N_2 share U and have independent V_1 and V_2, then Cov(N_1, N_2) = Var(U) = aθ².

**Cited for.** The simulation gives windows of one episode a shared rate component U while every window keeps the NB(5, 40) margin. With k = 5 and θ = 8 the correlation of two benign counts in one episode is 64a/360.

## P11. Logic of the interval decision rules [E]

**Statement.** Let L ≤ U, Δ, and δ be real numbers.

1. It is not the case that both U ≤ Δ and L > Δ.
2. If δ > Δ and U ≤ Δ, then δ is not in [L, U].
3. If δ ≤ Δ and L > Δ, then δ is not in [L, U].
4. If δ ≤ 0 and L > 0, then δ is not in [L, U].

**Corollary.** Let L and U be random with P(L ≤ δ ≤ U) ≥ 1 − α for the true δ. Then the verdict “support” (U ≤ Δ) has probability at most α when δ > Δ, the verdict “against” (L > Δ) has probability at most α when δ ≤ Δ, and “the interval excludes zero from above” (L > 0) has probability at most α when δ ≤ 0. The three verdicts support, against, and inconclusive are mutually exclusive and exhaustive by item 1.

**Cited for.** The H2-volume equivalence rule with Δ = 0.05 and the H2-sensitive rule (lower end above zero).

**What is not a theorem here.** The corollary needs an interval with coverage 1 − α. The design uses a percentile cluster bootstrap over calibration and FINAL episodes, and its coverage with 12 calibration episodes and 4 to 6 FINAL episodes per block is a numeric result [N] from the seeded simulation, reported in `v2.1-computation/RUN-RECORD.json`. It is approximate, and the design says so.

## P12. Standardization removes a common scale factor [E]

**Statement.** For real x and m, and real c > 0 and s > 0, (cx − cm)/(cs) = (x − m)/s. If a sample has mean m and standard deviation s, the sample multiplied by c has mean cm and standard deviation cs.

**Cited for.** In the hybrid FedAvg arm where the contributor does not rescale, each client standardizes with its own benign moments. A count feature at one quarter of the scale then has the same standardized value as the rescaled feature with local moments. That arm is therefore not predicted to collapse.

## P13. Per-record recall ceiling [S]

FROM-SOURCE: `recall_ceiling`, machine-checked for the per-record statement (`rq2-sampling-analysis-20261115/ANALYSIS.md` section 4, as cited in `DESIGN.v2.md` section M). Unchanged in v2.1. It bounds memoryless per-record rules on records that share an identical key. Its use here, as the reason the per-record arm degrades under pS, is an interpretation and not a new theorem.

---

## Numeric results only [N]

These values are cited in the design. None is a general theorem.

| Result | Value | How obtained | Certifiable exactly |
|---|---|---|---|
| p0 threshold, benign NB(5, 40) | 96, with P(B ≤ 95) = 0.989539 < 0.99 ≤ P(B ≤ 96) = 0.990355 | exact sum | yes, a finite sum of rationals with q = 1/9; the script checks both inequalities with exact fractions |
| pS threshold, benign sampled NB(5, 10) | 26 sampled packets, 104 rescaled, with P(S ≤ 25) = 0.987770 < 0.99 ≤ P(S ≤ 26) = 0.990748 | exact sum | yes, with q = 1/3; checked with exact fractions |
| Achieved FPR at the two thresholds | 0.009645 (p0), 0.009252 (pS) | exact sum | yes |
| FPR of the frozen p0 threshold on rescaled pS benign | P(4S > 96) = P(S > 24) = 0.016100 | exact sum | yes |
| Predicted recall table (section I of the design) | see the design | exact convolution of NB and Poisson mass functions | no, the Poisson terms contain e^(−λ); numeric to about 10⁻¹² |
| Recall of the unscaled mismatch arm | at most 2.6 × 10⁻⁴ at every ratio, the largest at r = 5 | exact convolution | no |
| Design effect of the paired difference under an episode share a of the benign rate | a = 4: 4.2, 3.2, 5.0 at r = 1.5, 2.0, 2.5; a = 1: 1.4, 1.4, 1.9 | numerical integration over the episode component | no |
| Expected distinct hosts from the bin total | see the design | closed form in P6 (d), evaluated numerically | no |
| Power, false-exclusion rates, and verdict probabilities | see `v2.1-computation/RUN-RECORD.json` | seeded simulation | no |

## Suggested order for the Lean check

P11 and P12 are order and field identities. P8 and P9 (a) are finite variance identities. P1, P2, and P3 need binomial moments and the law of total variance. P7 (a) is a counting fact about order statistics. P4, P5, P6 (d), P7 (b), P9 (b), and P10 need more probability theory (generating functions, Poisson thinning, exchangeability, gamma convolution) and can be cited from standard references if formalising them is out of proportion.
