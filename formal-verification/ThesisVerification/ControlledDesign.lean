module

public import Mathlib.Algebra.BigOperators.Field
public import Mathlib.Data.Nat.Choose.Sum
public import Mathlib.Data.Finset.Sum
public import Mathlib.Analysis.Real.Sqrt
public import Mathlib.Analysis.SpecificLimits.Normed
public import Mathlib.Analysis.SpecialFunctions.Exponential
public import Mathlib.Tactic.Linarith
public import Mathlib.Tactic.NormNum
public import ThesisVerification.Sampling
public import ThesisVerification.Foundations

public section

set_option warningAsError true

/-!
Source: the propositions of the controlled-study design v2.1,
`option3-design-20261115/PROPOSITIONS-FOR-LEAN.v2.1.md` (P1 to P12 and the
table of numeric results). `design-source-map.json` gives the locator, meaning,
assumptions, and scope of every theorem.

All statements are exact and data-free. Independent selection of each packet
with probability `p` is the product weight `selWeight` on sets of selected
packets, as in `ThesisVerification/Sampling.lean`. A count that can be
arbitrarily large (the number of packets in a bin) is described by its mass
function on the natural numbers, and an expectation over it is an
unconditional sum (`HasSum`). Other random variables live on a finite sample
space with weights. The theorems do not establish that the keyed selector
behaves as independent selection, they use no measured count, and they do not
concern any learned model.

Limits of this module. P4 is proved for an integer size `k ≥ 1`, not for a
real size. P6 (d) gives the probability that one Poisson source is seen and
adds it over the sources; the joint law of the sources is not modeled. P7 (b),
P8, P9, and the finite form of the P11 corollary use a finite sample space;
the P11 corollary is also proved for any probability measure. Of P10 only the
parts that need no integral are proved: the sum of two Gamma variables, the
Poisson-Gamma mixture, and the Gamma variance are not formalized, because the
integral and Gamma-function modules of Mathlib are not in the local cache.
-/

namespace ThesisVerification.ControlledDesign

open scoped BigOperators

/-! ## Independent selection on a finite set of packets -/

/-- Weight of one selection pattern: `T` is the set of selected packets, each
packet is selected with probability `p` and dropped with probability `1 − p`,
independently. The packets are indexed by any finite type. -/
noncomputable def selWeight (p : ℝ) {ι : Type*} [Fintype ι] [DecidableEq ι] (T : Finset ι) : ℝ :=
  ∏ i : ι, if i ∈ T then p else 1 - p

/-- Binomial mass: exactly `s` of `n` packets are selected. -/
noncomputable def binomPMF (n : ℕ) (p : ℝ) (s : ℕ) : ℝ :=
  (n.choose s : ℝ) * p ^ s * (1 - p) ^ (n - s)

/-- Sum over all subsets of a product whose factor at `i` depends on whether
`i` is in the subset. -/
theorem sum_prod_ite {ι : Type*} [Fintype ι] [DecidableEq ι] (a b : ι → ℝ) :
    ∑ T : Finset ι, ∏ i : ι, (if i ∈ T then a i else b i) = ∏ i : ι, (a i + b i) := by
  rw [Finset.prod_add, Finset.powerset_univ]
  refine Finset.sum_congr rfl fun T _ => ?_
  rw [Finset.prod_ite]
  congr 1
  · refine Finset.prod_congr ?_ fun _ _ => rfl
    ext i
    simp
  · refine Finset.prod_congr ?_ fun _ _ => rfl
    ext i
    simp

/-- Expectation of a product of per-packet factors under independent
selection: the factors separate. This is the independence of the selections. -/
theorem selWeight_test {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (x y : ι → ℝ) :
    ∑ T : Finset ι, selWeight p T * ∏ i : ι, (if i ∈ T then x i else y i)
      = ∏ i : ι, (p * x i + (1 - p) * y i) := by
  rw [← sum_prod_ite]
  refine Finset.sum_congr rfl fun T _ => ?_
  unfold selWeight
  rw [← Finset.prod_mul_distrib]
  refine Finset.prod_congr rfl fun i _ => ?_
  split_ifs <;> rfl

/-- The selection weights add up to one. -/
theorem selWeight_sum_one {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) :
    ∑ T : Finset ι, selWeight p T = 1 := by
  simpa using selWeight_test p (fun _ : ι => (1 : ℝ)) (fun _ => 1)

/-- The weight of a pattern depends only on how many packets it selects. -/
theorem selWeight_eq {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (T : Finset ι) :
    selWeight p T = p ^ T.card * (1 - p) ^ (Fintype.card ι - T.card) := by
  unfold selWeight
  rw [Finset.prod_ite, Finset.prod_const, Finset.prod_const]
  have h1 : (Finset.univ.filter fun i : ι => i ∈ T) = T := by
    ext i
    simp
  have h2 : (Finset.univ.filter fun i : ι => i ∉ T) = Tᶜ := by
    ext i
    simp
  rw [h1, h2, Finset.card_compl]

/-- With `0 ≤ p ≤ 1` every selection weight is nonnegative. -/
theorem selWeight_nonneg {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (hp0 : 0 ≤ p)
    (hp1 : p ≤ 1) (T : Finset ι) : 0 ≤ selWeight p T := by
  rw [selWeight_eq]
  have : (0 : ℝ) ≤ 1 - p := by linarith
  positivity

/-- On packets indexed by `Fin n` the weight is the pattern weight of
`ThesisVerification/Sampling.lean`. -/
theorem selWeight_eq_patternWeight (p : ℝ) {n : ℕ} (T : Finset (Fin n)) :
    selWeight p T = Sampling.patternWeight p T := by
  rw [selWeight_eq, Sampling.patternWeight_eq, Fintype.card_fin]

/-- All packets of a set `A` are selected with probability `p ^ |A|`. -/
theorem prob_all_selected {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (A : Finset ι) :
    ∑ T : Finset ι, selWeight p T * (if A ⊆ T then 1 else 0) = p ^ A.card := by
  have h := selWeight_test p (fun _ : ι => (1 : ℝ)) (fun i => if i ∈ A then 0 else 1)
  have hL : ∀ T : Finset ι,
      ∏ i : ι, (if i ∈ T then (1 : ℝ) else (if i ∈ A then 0 else 1))
        = if A ⊆ T then 1 else 0 := by
    intro T
    by_cases hAT : A ⊆ T
    · rw [ite_eq_left hAT]
      refine Finset.prod_eq_one fun i _ => ?_
      by_cases hi : i ∈ T
      · simp [hi]
      · have hiA : i ∉ A := fun hA => hi (hAT hA)
        simp [hi, hiA]
    · rw [ite_eq_right hAT]
      obtain ⟨j, hjA, hjT⟩ := Finset.not_subset.mp hAT
      exact Finset.prod_eq_zero (Finset.mem_univ j) (by simp [hjA, hjT])
  have hR : ∏ i : ι, (p * 1 + (1 - p) * (if i ∈ A then (0 : ℝ) else 1)) = p ^ A.card := by
    have hterm : ∀ i : ι, (p * 1 + (1 - p) * (if i ∈ A then (0 : ℝ) else 1))
        = if i ∈ A then p else 1 := by
      intro i
      split_ifs <;> ring
    simp_rw [hterm]
    rw [Finset.prod_ite_mem, Finset.univ_inter, Finset.prod_const]
  simp_rw [hL] at h
  rw [h, hR]

/-- No packet of a set `A` is selected with probability `(1 − p) ^ |A|`. -/
theorem prob_none_selected {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (A : Finset ι) :
    ∑ T : Finset ι, selWeight p T * (if Disjoint A T then 1 else 0) = (1 - p) ^ A.card := by
  have h := selWeight_test p (fun i : ι => if i ∈ A then (0 : ℝ) else 1) (fun _ => 1)
  have hL : ∀ T : Finset ι,
      ∏ i : ι, (if i ∈ T then (if i ∈ A then (0 : ℝ) else 1) else 1)
        = if Disjoint A T then 1 else 0 := by
    intro T
    by_cases hAT : Disjoint A T
    · rw [ite_eq_left hAT]
      refine Finset.prod_eq_one fun i _ => ?_
      by_cases hi : i ∈ T
      · have hiA : i ∉ A := fun hA => Finset.disjoint_left.mp hAT hA hi
        simp [hi, hiA]
      · simp [hi]
    · rw [ite_eq_right hAT]
      obtain ⟨j, hjA, hjT⟩ := Finset.not_disjoint_iff.mp hAT
      exact Finset.prod_eq_zero (Finset.mem_univ j) (by simp [hjA, hjT])
  have hR : ∏ i : ι, (p * (if i ∈ A then (0 : ℝ) else 1) + (1 - p) * 1) = (1 - p) ^ A.card := by
    have hterm : ∀ i : ι, (p * (if i ∈ A then (0 : ℝ) else 1) + (1 - p) * 1)
        = if i ∈ A then 1 - p else 1 := by
      intro i
      split_ifs <;> ring
    simp_rw [hterm]
    rw [Finset.prod_ite_mem, Finset.univ_inter, Finset.prod_const]
  simp_rw [hL] at h
  rw [h, hR]

/-- One given packet is selected with probability `p`. -/
theorem prob_selected {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (j : ι) :
    ∑ T : Finset ι, selWeight p T * (if j ∈ T then 1 else 0) = p := by
  simpa using prob_all_selected p ({j} : Finset ι)

/-- Two different packets are both selected with probability `p²`, the product
of the two single probabilities. -/
theorem prob_pair_selected {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (i j : ι)
    (hij : i ≠ j) :
    ∑ T : Finset ι, selWeight p T * ((if i ∈ T then 1 else 0) * (if j ∈ T then 1 else 0))
      = p ^ 2 := by
  have h := prob_all_selected p ({i, j} : Finset ι)
  rw [Finset.card_pair hij] at h
  rw [← h]
  refine Finset.sum_congr rfl fun T _ => ?_
  by_cases hi : i ∈ T <;> by_cases hj : j ∈ T <;> simp [Finset.insert_subset_iff, hi, hj]

/-- The sum of the weights of the selected packets, written with indicators. -/
theorem selected_sum_eq_indicator {ι : Type*} [Fintype ι] [DecidableEq ι] (w : ι → ℝ)
    (T : Finset ι) : ∑ i ∈ T, w i = ∑ i : ι, w i * (if i ∈ T then 1 else 0) := by
  simp [Finset.sum_ite_mem]

/-- Mean of the weighted selected total: `E[Σ wᵢ Iᵢ] = p Σ wᵢ`. -/
theorem weighted_selected_mean {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (w : ι → ℝ) :
    ∑ T : Finset ι, selWeight p T * ∑ i ∈ T, w i = p * ∑ i : ι, w i := by
  have h1 : ∀ T : Finset ι, selWeight p T * ∑ i ∈ T, w i
      = ∑ i : ι, w i * (selWeight p T * (if i ∈ T then 1 else 0)) := by
    intro T
    rw [selected_sum_eq_indicator w T, Finset.mul_sum]
    exact Finset.sum_congr rfl fun i _ => by ring
  rw [Finset.sum_congr rfl fun T _ => h1 T, Finset.sum_comm, Finset.mul_sum]
  refine Finset.sum_congr rfl fun i _ => ?_
  rw [← Finset.mul_sum, prob_selected p i]
  ring

/-- Second moment of the weighted selected total:
`E[(Σ wᵢ Iᵢ)²] = p Σ wᵢ² + p² ((Σ wᵢ)² − Σ wᵢ²)`. -/
theorem weighted_selected_sq {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (w : ι → ℝ) :
    ∑ T : Finset ι, selWeight p T * (∑ i ∈ T, w i) ^ 2
      = p * ∑ i : ι, w i ^ 2 + p ^ 2 * ((∑ i : ι, w i) ^ 2 - ∑ i : ι, w i ^ 2) := by
  have hpair : ∀ i j : ι,
      ∑ T : Finset ι, selWeight p T * ((if i ∈ T then 1 else 0) * (if j ∈ T then 1 else 0))
        = p ^ 2 + (if i = j then p - p ^ 2 else 0) := by
    intro i j
    by_cases hij : i = j
    · subst hij
      rw [ite_eq_left rfl]
      calc ∑ T : Finset ι, selWeight p T * ((if i ∈ T then 1 else 0) * (if i ∈ T then 1 else 0))
          = ∑ T : Finset ι, selWeight p T * (if i ∈ T then 1 else 0) :=
            Finset.sum_congr rfl fun T _ => by by_cases hi : i ∈ T <;> simp [hi]
        _ = p := prob_selected p i
        _ = p ^ 2 + (p - p ^ 2) := by ring
    · rw [ite_eq_right hij, add_zero]
      exact prob_pair_selected p i j hij
  have hexp : ∀ T : Finset ι, selWeight p T * (∑ i ∈ T, w i) ^ 2
      = ∑ i : ι, ∑ j : ι, w i * w j
          * (selWeight p T * ((if i ∈ T then 1 else 0) * (if j ∈ T then 1 else 0))) := by
    intro T
    rw [selected_sum_eq_indicator w, sq, Finset.sum_mul_sum, Finset.mul_sum]
    refine Finset.sum_congr rfl fun i _ => ?_
    rw [Finset.mul_sum]
    refine Finset.sum_congr rfl fun j _ => ?_
    ring
  simp_rw [hexp]
  rw [Finset.sum_comm]
  have hstep : ∀ i : ι, ∑ T : Finset ι, ∑ j : ι, w i * w j
      * (selWeight p T * ((if i ∈ T then 1 else 0) * (if j ∈ T then 1 else 0)))
      = p ^ 2 * (w i * ∑ j : ι, w j) + (p - p ^ 2) * w i ^ 2 := by
    intro i
    rw [Finset.sum_comm]
    have hj : ∀ j : ι, ∑ T : Finset ι, w i * w j
        * (selWeight p T * ((if i ∈ T then 1 else 0) * (if j ∈ T then 1 else 0)))
        = p ^ 2 * (w i * w j) + (if i = j then (p - p ^ 2) * (w i * w j) else 0) := by
      intro j
      rw [← Finset.mul_sum, hpair i j]
      split_ifs <;> ring
    simp_rw [hj]
    rw [Finset.sum_add_distrib, Finset.sum_ite_eq, ite_eq_left (Finset.mem_univ i),
      ← Finset.mul_sum, ← Finset.mul_sum]
    ring
  simp_rw [hstep]
  rw [Finset.sum_add_distrib, ← Finset.mul_sum, ← Finset.mul_sum, ← Finset.sum_mul,
    sq (∑ i : ι, w i)]
  ring

/-- The law of the number of selected packets is binomial: the expectation of
any function of the count is its sum against the binomial mass function. -/
theorem count_law {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (g : ℕ → ℝ) :
    ∑ T : Finset ι, selWeight p T * g T.card
      = ∑ s ∈ Finset.range (Fintype.card ι + 1), binomPMF (Fintype.card ι) p s * g s := by
  simp_rw [selWeight_eq]
  have h := Finset.sum_powerset_apply_card
    (fun m => p ^ m * (1 - p) ^ (Fintype.card ι - m) * g m) (x := (Finset.univ : Finset ι))
  rw [Finset.powerset_univ, Finset.card_univ] at h
  rw [h]
  refine Finset.sum_congr rfl fun s _ => ?_
  rw [nsmul_eq_mul]
  unfold binomPMF
  ring

/-- The binomial mass is the total weight of the patterns that select exactly
`s` packets (`Sampling.retained_count_binomial`). -/
theorem binomPMF_eq_pattern_sum (p : ℝ) (n s : ℕ) :
    binomPMF n p s
      = ∑ T ∈ (Finset.univ : Finset (Fin n)).powersetCard s, Sampling.patternWeight p T := by
  rw [Sampling.retained_count_binomial]
  rfl

/-- The binomial masses add up to one. -/
theorem binomPMF_sum_one (n : ℕ) (p : ℝ) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s = 1 := by
  have h := count_law (ι := Fin n) p (fun _ => 1)
  simp only [mul_one, Fintype.card_fin] at h
  rw [← h, selWeight_sum_one]

/-- Binomial mean: `E[S | N = n] = n p`. -/
theorem binomPMF_mean (n : ℕ) (p : ℝ) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s * (s : ℝ) = n * p := by
  have h := count_law (ι := Fin n) p (fun s => (s : ℝ))
  simp only [Fintype.card_fin] at h
  rw [← h]
  have hw := weighted_selected_mean (ι := Fin n) p (fun _ => 1)
  simp only [Finset.sum_const, Finset.card_univ, Fintype.card_fin, nsmul_eq_mul, mul_one] at hw
  rw [hw]
  ring

/-- Binomial second moment: `E[S² | N = n] = n p (1 − p) + (n p)²`. -/
theorem binomPMF_second_moment (n : ℕ) (p : ℝ) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s * (s : ℝ) ^ 2 = n * p * (1 - p) + (n * p) ^ 2 := by
  have h := count_law (ι := Fin n) p (fun s => (s : ℝ) ^ 2)
  simp only [Fintype.card_fin] at h
  rw [← h]
  have hw := weighted_selected_sq (ι := Fin n) p (fun _ => 1)
  simp only [Finset.sum_const, Finset.card_univ, Fintype.card_fin, nsmul_eq_mul, mul_one,
    one_pow] at hw
  rw [hw]
  ring

/-- Mean square of the rescaled count about any centre `c`, given `N = n`:
`E[(S/p − c)² | N = n] = n (1 − p)/p + (n − c)²`. -/
theorem binomPMF_rescaled_second_moment (n : ℕ) (p c : ℝ) (hp : p ≠ 0) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p - c) ^ 2
      = n * (1 - p) / p + ((n : ℝ) - c) ^ 2 := by
  have h0 := binomPMF_sum_one n p
  have h1 := binomPMF_mean n p
  have h2 := binomPMF_second_moment n p
  have hexp : ∀ s : ℕ, binomPMF n p s * ((s : ℝ) / p - c) ^ 2
      = (1 / p ^ 2) * (binomPMF n p s * (s : ℝ) ^ 2)
        - (2 * c / p) * (binomPMF n p s * (s : ℝ)) + c ^ 2 * binomPMF n p s := by
    intro s
    field_simp
    ring
  simp_rw [hexp]
  rw [Finset.sum_add_distrib, Finset.sum_sub_distrib, ← Finset.mul_sum, ← Finset.mul_sum,
    ← Finset.mul_sum, h0, h1, h2]
  field_simp
  ring

/-! ## P1. The rescaled count is unbiased -/

/-- P1, conditional form: `E[S/p | N = n] = n` for `S | N = n` binomial. -/
theorem p1_conditional_unbiased (n : ℕ) (p : ℝ) (hp : p ≠ 0) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p) = n := by
  have h := binomPMF_mean n p
  have hdiv : ∀ s : ℕ, binomPMF n p s * ((s : ℝ) / p) = (binomPMF n p s * (s : ℝ)) / p :=
    fun s => by ring
  simp_rw [hdiv]
  rw [← Finset.sum_div, h]
  field_simp

/-- P1 for a count `N` with finite support: `E[S/p] = E[N]`, where `f n` is the
mass of `N = n`. -/
theorem p1_unbiased_finite (support : Finset ℕ) (f : ℕ → ℝ) (p : ℝ) (hp : p ≠ 0) :
    ∑ n ∈ support, f n * ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p)
      = ∑ n ∈ support, f n * (n : ℝ) := by
  refine Finset.sum_congr rfl fun n _ => ?_
  rw [p1_conditional_unbiased n p hp]

/-- P1 for any count `N` on the natural numbers with a finite mean `m`:
`E[S/p] = E[N]`. The expectation of `S/p` is the sum over `n` of the mass of
`N = n` times the conditional expectation. -/
theorem p1_unbiased (f : ℕ → ℝ) (p m : ℝ) (hp : p ≠ 0)
    (hmean : HasSum (fun n : ℕ => f n * (n : ℝ)) m) :
    HasSum (fun n : ℕ => f n * ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p))
      m := by
  have hfun : (fun n : ℕ => f n * ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p))
      = fun n : ℕ => f n * (n : ℝ) := by
    funext n
    rw [p1_conditional_unbiased n p hp]
  rw [hfun]
  exact hmean

/-- P1 at `p = 1/4`: `E[4S] = E[N]`. -/
theorem p1_quarter (f : ℕ → ℝ) (m : ℝ) (hmean : HasSum (fun n : ℕ => f n * (n : ℝ)) m) :
    HasSum (fun n : ℕ => f n * ∑ s ∈ Finset.range (n + 1), binomPMF n (1 / 4) s * (4 * (s : ℝ)))
      m := by
  have h := p1_unbiased f (1 / 4) m (by norm_num) hmean
  have h4 : ∀ s : ℕ, (s : ℝ) / (1 / 4) = 4 * (s : ℝ) := fun s => by ring
  simpa only [h4] using h

/-- P1, weighted form: `E[(1/p) Σ wᵢ Iᵢ] = Σ wᵢ` for fixed weights `w` and
independent selection indicators. -/
theorem p1_weighted_unbiased {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (hp : p ≠ 0)
    (w : ι → ℝ) :
    ∑ T : Finset ι, selWeight p T * ((1 / p) * ∑ i ∈ T, w i) = ∑ i : ι, w i := by
  have h := weighted_selected_mean p w
  have hmul : ∀ T : Finset ι, selWeight p T * ((1 / p) * ∑ i ∈ T, w i)
      = (1 / p) * (selWeight p T * ∑ i ∈ T, w i) := fun T => by ring
  simp_rw [hmul]
  rw [← Finset.mul_sum, h]
  field_simp

/-- Packets ×4 is unbiased at `p = 1/4`: the expected value of four times the
number of selected packets is the number of packets. -/
theorem p1_packets_times_four {ι : Type*} [Fintype ι] [DecidableEq ι] :
    ∑ T : Finset ι, selWeight (1 / 4) T * (4 * (T.card : ℝ)) = (Fintype.card ι : ℝ) := by
  have h := p1_weighted_unbiased (ι := ι) (1 / 4) (by norm_num) (fun _ => 1)
  simp only [Finset.sum_const, nsmul_eq_mul, mul_one, Finset.card_univ] at h
  rw [← h]
  refine Finset.sum_congr rfl fun T _ => ?_
  ring

/-- Bytes ×4 is unbiased at `p = 1/4`, whatever the packet sizes are. -/
theorem p1_bytes_times_four {ι : Type*} [Fintype ι] [DecidableEq ι] (size : ι → ℝ) :
    ∑ T : Finset ι, selWeight (1 / 4) T * (4 * ∑ i ∈ T, size i) = ∑ i : ι, size i := by
  have h := p1_weighted_unbiased (ι := ι) (1 / 4) (by norm_num) size
  rw [← h]
  refine Finset.sum_congr rfl fun T _ => ?_
  ring

/-- SYN ×4 is unbiased at `p = 1/4`: the expected value of four times the
number of selected SYN packets is the number of SYN packets. -/
theorem p1_syn_times_four {ι : Type*} [Fintype ι] [DecidableEq ι] (syn : ι → Prop)
    [DecidablePred syn] :
    ∑ T : Finset ι, selWeight (1 / 4) T * (4 * ((T.filter syn).card : ℝ))
      = ((Finset.univ.filter syn).card : ℝ) := by
  have h := p1_bytes_times_four (ι := ι) (fun i => if syn i then 1 else 0)
  simp only [Finset.sum_boole] at h
  exact h

/-! ## P2. Conditional variance and coefficient of variation -/

/-- P2: `Var(S/p | N = n) = n (1 − p)/p`. The centre `n` is the conditional
mean of `S/p` by `p1_conditional_unbiased`. -/
theorem p2_conditional_variance (n : ℕ) (p : ℝ) (hp : p ≠ 0) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p - (n : ℝ)) ^ 2
      = n * (1 - p) / p := by
  rw [binomPMF_rescaled_second_moment n p n hp]
  ring

/-- P2 at `p = 1/4`: `Var(4S | N = n) = 3n`. -/
theorem p2_quarter_variance (n : ℕ) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n (1 / 4) s * (4 * (s : ℝ) - (n : ℝ)) ^ 2
      = 3 * (n : ℝ) := by
  have h := p2_conditional_variance n (1 / 4) (by norm_num)
  have h4 : ∀ s : ℕ, (s : ℝ) / (1 / 4) = 4 * (s : ℝ) := fun s => by ring
  simp only [h4] at h
  rw [h]
  ring

/-- P2: for `n > 0` the coefficient of variation of `4S` given `N = n`, the
standard deviation `√(3n)` over the mean `n`, is `√(3/n)`. -/
theorem p2_cv_quarter (n : ℕ) (hn : 0 < n) :
    Real.sqrt (3 * (n : ℝ)) / (n : ℝ) = Real.sqrt (3 / (n : ℝ)) := by
  have hn' : (0 : ℝ) < n := by exact_mod_cast hn
  have h3 : 3 * (n : ℝ) = (3 / (n : ℝ)) * ((n : ℝ) * (n : ℝ)) := by field_simp
  rw [h3, Real.sqrt_mul' _ (mul_self_nonneg (n : ℝ)), Real.sqrt_mul_self hn'.le]
  field_simp

/-- P2: `n ≥ 300` gives a coefficient of variation of at most 0.1, and
`n ≥ 1200` gives at most 0.05. -/
theorem p2_cv_bounds (n : ℕ) :
    (300 ≤ n → Real.sqrt (3 / (n : ℝ)) ≤ 0.1) ∧ (1200 ≤ n → Real.sqrt (3 / (n : ℝ)) ≤ 0.05) := by
  constructor
  · intro hn
    have hn' : (300 : ℝ) ≤ n := by exact_mod_cast hn
    rw [Real.sqrt_le_iff]
    refine ⟨by norm_num, ?_⟩
    rw [div_le_iff₀ (by linarith)]
    norm_num
    linarith
  · intro hn
    have hn' : (1200 : ℝ) ≤ n := by exact_mod_cast hn
    rw [Real.sqrt_le_iff]
    refine ⟨by norm_num, ?_⟩
    rw [div_le_iff₀ (by linarith)]
    norm_num
    linarith

/-- P2, weighted form: `Var((1/p) Σ wᵢ Iᵢ) = ((1 − p)/p) Σ wᵢ²`. The centre
`Σ wᵢ` is the mean by `p1_weighted_unbiased`. -/
theorem p2_weighted_variance {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (hp : p ≠ 0)
    (w : ι → ℝ) :
    ∑ T : Finset ι, selWeight p T * ((1 / p) * ∑ i ∈ T, w i - ∑ i : ι, w i) ^ 2
      = ((1 - p) / p) * ∑ i : ι, w i ^ 2 := by
  have h0 := selWeight_sum_one (ι := ι) p
  have h1 := weighted_selected_mean p w
  have h2 := weighted_selected_sq p w
  have hexp : ∀ T : Finset ι, selWeight p T * ((1 / p) * ∑ i ∈ T, w i - ∑ i : ι, w i) ^ 2
      = (1 / p ^ 2) * (selWeight p T * (∑ i ∈ T, w i) ^ 2)
        - (2 * (∑ i : ι, w i) / p) * (selWeight p T * ∑ i ∈ T, w i)
        + (∑ i : ι, w i) ^ 2 * selWeight p T := by
    intro T
    field_simp
    ring
  simp_rw [hexp]
  rw [Finset.sum_add_distrib, Finset.sum_sub_distrib, ← Finset.mul_sum, ← Finset.mul_sum,
    ← Finset.mul_sum, h0, h1, h2]
  field_simp
  ring

/-- P2, weighted bound: with `0 ≤ wᵢ ≤ b_max` the variance is at most
`((1 − p)/p) · b_max · Σ wᵢ`. -/
theorem p2_weighted_variance_le {ι : Type*} [Fintype ι] [DecidableEq ι] (p : ℝ) (hp0 : 0 < p)
    (hp1 : p ≤ 1) (w : ι → ℝ) (bmax : ℝ) (hw0 : ∀ i, 0 ≤ w i) (hw1 : ∀ i, w i ≤ bmax) :
    ∑ T : Finset ι, selWeight p T * ((1 / p) * ∑ i ∈ T, w i - ∑ i : ι, w i) ^ 2
      ≤ ((1 - p) / p) * (bmax * ∑ i : ι, w i) := by
  rw [p2_weighted_variance p hp0.ne' w]
  have hcoef : 0 ≤ (1 - p) / p := div_nonneg (by linarith) hp0.le
  refine mul_le_mul_of_nonneg_left ?_ hcoef
  rw [Finset.mul_sum]
  refine Finset.sum_le_sum fun i _ => ?_
  rw [sq]
  exact mul_le_mul_of_nonneg_right (hw1 i) (hw0 i)

/-- P2, weighted form at `p = 1/4`: the variance of four times the selected
total is `3 Σ wᵢ²`, which is at most `3 · b_max · Σ wᵢ`. -/
theorem p2_weighted_quarter {ι : Type*} [Fintype ι] [DecidableEq ι] (w : ι → ℝ) (bmax : ℝ)
    (hw0 : ∀ i, 0 ≤ w i) (hw1 : ∀ i, w i ≤ bmax) :
    ∑ T : Finset ι, selWeight (1 / 4) T * (4 * ∑ i ∈ T, w i - ∑ i : ι, w i) ^ 2
        = 3 * ∑ i : ι, w i ^ 2 ∧
      ∑ T : Finset ι, selWeight (1 / 4) T * (4 * ∑ i ∈ T, w i - ∑ i : ι, w i) ^ 2
        ≤ 3 * bmax * ∑ i : ι, w i := by
  have heq := p2_weighted_variance (ι := ι) (1 / 4) (by norm_num) w
  have hle := p2_weighted_variance_le (ι := ι) (1 / 4) (by norm_num) (by norm_num) w bmax hw0 hw1
  have h4 : (1 : ℝ) / (1 / 4) = 4 := by norm_num
  have h3 : (1 - (1 : ℝ) / 4) / (1 / 4) = 3 := by norm_num
  rw [h4, h3] at heq hle
  exact ⟨heq, by linarith⟩

/-- P2, coefficient of variation of the byte estimator at `p = 1/4`: with
`n` packets, `0 ≤ wᵢ ≤ b_max`, a positive total, and `b_avg = (Σ wᵢ)/n`, the
standard deviation over the mean is at most `√(3/n) · √(b_max/b_avg)`. -/
theorem p2_bytes_cv_le {ι : Type*} [Fintype ι] [DecidableEq ι] (w : ι → ℝ) (bmax : ℝ)
    (hw0 : ∀ i, 0 ≤ w i) (hw1 : ∀ i, w i ≤ bmax) (htot : 0 < ∑ i : ι, w i) :
    Real.sqrt (∑ T : Finset ι, selWeight (1 / 4) T * (4 * ∑ i ∈ T, w i - ∑ i : ι, w i) ^ 2)
        / ∑ i : ι, w i
      ≤ Real.sqrt (3 / (Fintype.card ι : ℝ))
        * Real.sqrt (bmax / ((∑ i : ι, w i) / (Fintype.card ι : ℝ))) := by
  have hvar := (p2_weighted_quarter w bmax hw0 hw1).2
  have hn : (0 : ℝ) < (Fintype.card ι : ℝ) := by
    have hne : (Finset.univ : Finset ι).Nonempty := by
      by_contra hempty
      rw [Finset.not_nonempty_iff_eq_empty] at hempty
      rw [hempty, Finset.sum_empty] at htot
      exact lt_irrefl 0 htot
    have hcard : 0 < (Finset.univ : Finset ι).card := Finset.card_pos.mpr hne
    rw [Finset.card_univ] at hcard
    exact_mod_cast hcard
  rw [← Real.sqrt_mul (by positivity)]
  have hrhs : 3 / (Fintype.card ι : ℝ) * (bmax / ((∑ i : ι, w i) / (Fintype.card ι : ℝ)))
      = 3 * bmax / ∑ i : ι, w i := by
    field_simp
  rw [hrhs, div_le_iff₀ htot]
  have hW : Real.sqrt (3 * bmax / ∑ i : ι, w i) * ∑ i : ι, w i
      = Real.sqrt (3 * bmax * ∑ i : ι, w i) := by
    have h3 : 3 * bmax * ∑ i : ι, w i
        = (3 * bmax / ∑ i : ι, w i) * ((∑ i : ι, w i) * ∑ i : ι, w i) := by
      field_simp
    rw [h3, Real.sqrt_mul' _ (mul_self_nonneg _), Real.sqrt_mul_self htot.le]
  rw [hW]
  exact Real.sqrt_le_sqrt hvar

/-! ## P3. Variance of the rescaled count when the count itself is random -/

/-- P3 for a count `N` with finite support, about any centre `c`. With
`c = E[N]` and masses that add up to one this is
`Var(S/p) = Var(N) + ((1 − p)/p) E[N]`. -/
theorem p3_total_variance_finite (support : Finset ℕ) (f : ℕ → ℝ) (p c : ℝ) (hp : p ≠ 0) :
    ∑ n ∈ support, f n * ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p - c) ^ 2
      = ∑ n ∈ support, f n * ((n : ℝ) - c) ^ 2
        + ((1 - p) / p) * ∑ n ∈ support, f n * (n : ℝ) := by
  rw [Finset.mul_sum, ← Finset.sum_add_distrib]
  refine Finset.sum_congr rfl fun n _ => ?_
  rw [binomPMF_rescaled_second_moment n p c hp]
  ring

/-- P3 for any count `N` on the natural numbers with mean `μ` and variance
`v`: `Var(S/p) = Var(N) + ((1 − p)/p) E[N]`. The centre `μ` is the mean of
`S/p` by `p1_unbiased`. -/
theorem p3_total_variance (f : ℕ → ℝ) (p μ v : ℝ) (hp : p ≠ 0)
    (hmean : HasSum (fun n : ℕ => f n * (n : ℝ)) μ)
    (hvar : HasSum (fun n : ℕ => f n * ((n : ℝ) - μ) ^ 2) v) :
    HasSum (fun n : ℕ =>
        f n * ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p - μ) ^ 2)
      (v + ((1 - p) / p) * μ) := by
  have h := hvar.add (hmean.mul_left ((1 - p) / p))
  have hfun : (fun n : ℕ =>
      f n * ∑ s ∈ Finset.range (n + 1), binomPMF n p s * ((s : ℝ) / p - μ) ^ 2)
      = fun n : ℕ => f n * ((n : ℝ) - μ) ^ 2 + (1 - p) / p * (f n * (n : ℝ)) := by
    funext n
    rw [binomPMF_rescaled_second_moment n p μ hp]
    ring
  rw [hfun]
  exact h

/-- P3 at `p = 1/4`: `Var(4S) = Var(N) + 3 E[N]`. -/
theorem p3_quarter (f : ℕ → ℝ) (μ v : ℝ)
    (hmean : HasSum (fun n : ℕ => f n * (n : ℝ)) μ)
    (hvar : HasSum (fun n : ℕ => f n * ((n : ℝ) - μ) ^ 2) v) :
    HasSum (fun n : ℕ =>
        f n * ∑ s ∈ Finset.range (n + 1), binomPMF n (1 / 4) s * (4 * (s : ℝ) - μ) ^ 2)
      (v + 3 * μ) := by
  have h := p3_total_variance f (1 / 4) μ v (by norm_num) hmean hvar
  have h4 : ∀ s : ℕ, (s : ℝ) / (1 / 4) = 4 * (s : ℝ) := fun s => by ring
  have h3 : (1 - (1 : ℝ) / 4) / (1 / 4) = 3 := by norm_num
  simpa only [h4, h3] using h

/-- P3, corollary: if `Var(N) = μ + φ μ²` with `E[N] = μ`, then
`Var(4S) = 4μ + φ μ²`. -/
theorem p3_overdispersed_quarter (f : ℕ → ℝ) (μ φ : ℝ)
    (hmean : HasSum (fun n : ℕ => f n * (n : ℝ)) μ)
    (hvar : HasSum (fun n : ℕ => f n * ((n : ℝ) - μ) ^ 2) (μ + φ * μ ^ 2)) :
    HasSum (fun n : ℕ =>
        f n * ∑ s ∈ Finset.range (n + 1), binomPMF n (1 / 4) s * (4 * (s : ℝ) - μ) ^ 2)
      (4 * μ + φ * μ ^ 2) := by
  have h := p3_quarter f μ (μ + φ * μ ^ 2) hmean hvar
  have hval : μ + φ * μ ^ 2 + 3 * μ = 4 * μ + φ * μ ^ 2 := by ring
  rw [hval] at h
  exact h

/-- P3, numbers: `μ = 40` and `φ = 0.2` give `Var(N) = 360` and
`Var(4S) = 480`. -/
theorem p3_numbers :
    (40 : ℝ) + 0.2 * 40 ^ 2 = 360 ∧ 4 * (40 : ℝ) + 0.2 * 40 ^ 2 = 480 := by
  norm_num

/-! ## Series tools -/

/-- A series whose first `s` terms vanish has the sum of its shifted series. -/
theorem hasSum_of_shift (f : ℕ → ℝ) (s : ℕ) (a : ℝ) (hzero : ∀ n, n < s → f n = 0)
    (h : HasSum (fun m : ℕ => f (m + s)) a) : HasSum f a := by
  rw [← hasSum_nat_add_iff' s]
  have h0 : ∑ i ∈ Finset.range s, f i = 0 :=
    Finset.sum_eq_zero fun i hi => hzero i (Finset.mem_range.mp hi)
  rw [h0, sub_zero]
  exact h

/-- The negative binomial series `Σ C(m + K, K) xᵐ = (1 − x)^(−(K+1))` for
`0 ≤ x < 1`. -/
theorem choose_geometric_hasSum (K : ℕ) (x : ℝ) (hx0 : 0 ≤ x) (hx1 : x < 1) :
    HasSum (fun m : ℕ => ((m + K).choose K : ℝ) * x ^ m) (1 / (1 - x) ^ (K + 1)) := by
  refine hasSum_choose_mul_geometric_of_norm_lt_one K ?_
  rw [Real.norm_eq_abs, abs_lt]
  constructor <;> linarith

/-- The exponential series of a real number. -/
theorem real_exp_hasSum (x : ℝ) :
    HasSum (fun n : ℕ => x ^ n / (n.factorial : ℝ)) (Real.exp x) := by
  rw [Real.exp_eq_exp_ℝ]
  exact NormedSpace.expSeries_div_hasSum_exp x

/-! ## P4. A thinned negative binomial is negative binomial with the same size -/

/-- Negative binomial mass with integer size `k ≥ 1` and mean `μ`:
`C(n + k − 1, k − 1) qᵏ (1 − q)ⁿ` with `q = k/(k + μ)`. For integer `k` the
coefficient equals `Γ(k + n)/(n! Γ(k))`. -/
noncomputable def nbPMF (k : ℕ) (μ : ℝ) (n : ℕ) : ℝ :=
  ((n + k - 1).choose (k - 1) : ℝ) * ((k : ℝ) / ((k : ℝ) + μ)) ^ k * (μ / ((k : ℝ) + μ)) ^ n

/-- The negative binomial masses add up to one. -/
theorem nbPMF_hasSum_one (k : ℕ) (hk : 1 ≤ k) (μ : ℝ) (hμ : 0 < μ) : HasSum (nbPMF k μ) 1 := by
  obtain ⟨K, rfl⟩ : ∃ K, k = K + 1 := ⟨k - 1, by omega⟩
  have hD : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) + μ := by positivity
  have hr0 : 0 ≤ μ / (((K + 1 : ℕ) : ℝ) + μ) := by positivity
  have hr1 : μ / (((K + 1 : ℕ) : ℝ) + μ) < 1 := by
    rw [div_lt_one hD]
    have : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) := by positivity
    linarith
  have h := (choose_geometric_hasSum K _ hr0 hr1).mul_left
    ((((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ)) ^ (K + 1))
  have hq : 1 - μ / (((K + 1 : ℕ) : ℝ) + μ) = ((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ) := by
    field_simp
    ring
  have hqpos : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ) := by positivity
  rw [hq, mul_one_div, div_self (pow_ne_zero _ hqpos.ne')] at h
  have hfun : nbPMF (K + 1) μ = fun m : ℕ =>
      (((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ)) ^ (K + 1)
        * (((m + K).choose K : ℝ) * (μ / (((K + 1 : ℕ) : ℝ) + μ)) ^ m) := by
    funext m
    unfold nbPMF
    have e1 : m + (K + 1) - 1 = m + K := by omega
    have e2 : K + 1 - 1 = K := by omega
    rw [e1, e2]
    ring
  rw [hfun]
  exact h

/-- The series behind P4, with the success probability written as `κ/(κ + μ)`
for any real `κ > 0`. -/
theorem thinned_nb_series (K s : ℕ) (κ μ p : ℝ) (hκ : 0 < κ) (hμ : 0 < μ) (hp0 : 0 < p)
    (hp1 : p ≤ 1) :
    HasSum (fun n : ℕ =>
        (((n + K).choose K : ℝ) * (κ / (κ + μ)) ^ (K + 1) * (μ / (κ + μ)) ^ n) * binomPMF n p s)
      (((s + K).choose K : ℝ) * (κ / (κ + p * μ)) ^ (K + 1) * (p * μ / (κ + p * μ)) ^ s) := by
  have hD : 0 < κ + μ := by positivity
  have hE : 0 < κ + p * μ := by positivity
  have hx0 : 0 ≤ μ / (κ + μ) * (1 - p) := mul_nonneg (by positivity) (by linarith)
  have hr1 : μ / (κ + μ) < 1 := by
    rw [div_lt_one hD]
    linarith
  have hx1 : μ / (κ + μ) * (1 - p) < 1 := by
    have h1 : μ / (κ + μ) * (1 - p) ≤ μ / (κ + μ) * 1 :=
      mul_le_mul_of_nonneg_left (by linarith) (by positivity)
    linarith
  have hser := (choose_geometric_hasSum (s + K) _ hx0 hx1).mul_left
    (((s + K).choose K : ℝ) * (κ / (κ + μ)) ^ (K + 1) * (μ / (κ + μ) * p) ^ s)
  have hval : ((s + K).choose K : ℝ) * (κ / (κ + μ)) ^ (K + 1) * (μ / (κ + μ) * p) ^ s
        * (1 / (1 - μ / (κ + μ) * (1 - p)) ^ (s + K + 1))
      = ((s + K).choose K : ℝ) * (κ / (κ + p * μ)) ^ (K + 1) * (p * μ / (κ + p * μ)) ^ s := by
    have hy : 1 - μ / (κ + μ) * (1 - p) = (κ + p * μ) / (κ + μ) := by
      field_simp
      ring
    have halg : ∀ (c q rp y : ℝ), y ≠ 0 → ∀ a b : ℕ,
        c * q ^ a * rp ^ b * (1 / y ^ (b + a)) = c * (q / y) ^ a * (rp / y) ^ b := by
      intro c q rp y hy0 a b
      rw [div_pow, div_pow, pow_add]
      field_simp
    have hy0 : (κ + p * μ) / (κ + μ) ≠ 0 := (div_pos hE hD).ne'
    have hexp : s + K + 1 = s + (K + 1) := by omega
    have hq : κ / (κ + μ) / ((κ + p * μ) / (κ + μ)) = κ / (κ + p * μ) := by
      field_simp
    have hr : μ / (κ + μ) * p / ((κ + p * μ) / (κ + μ)) = p * μ / (κ + p * μ) := by
      field_simp
    rw [hy, hexp, halg _ _ _ _ hy0, hq, hr]
  rw [hval] at hser
  refine hasSum_of_shift _ s _ ?_ ?_
  · intro n hn
    simp [binomPMF, Nat.choose_eq_zero_of_lt hn]
  · have hfun : (fun m : ℕ =>
          (((m + s + K).choose K : ℝ) * (κ / (κ + μ)) ^ (K + 1) * (μ / (κ + μ)) ^ (m + s))
            * binomPMF (m + s) p s)
        = fun m : ℕ => ((s + K).choose K : ℝ) * (κ / (κ + μ)) ^ (K + 1) * (μ / (κ + μ) * p) ^ s
            * (((m + (s + K)).choose (s + K) : ℝ) * (μ / (κ + μ) * (1 - p)) ^ m) := by
      funext m
      have h := Nat.choose_mul (n := m + s + K) (k := s + K) (s := K) (Nat.le_add_left K s)
      simp only [Nat.add_sub_cancel] at h
      have hchR : ((m + s + K).choose K : ℝ) * ((m + s).choose s : ℝ)
          = ((s + K).choose K : ℝ) * ((m + (s + K)).choose (s + K) : ℝ) := by
        rw [← add_assoc m s K]
        exact_mod_cast (by rw [← h, Nat.mul_comm] :
          (m + s + K).choose K * (m + s).choose s
            = (s + K).choose K * (m + s + K).choose (s + K))
      unfold binomPMF
      rw [Nat.add_sub_cancel, pow_add, mul_pow, mul_pow]
      linear_combination ((κ / (κ + μ)) ^ (K + 1) * (μ / (κ + μ)) ^ m * (μ / (κ + μ)) ^ s
        * p ^ s * (1 - p) ^ m) * hchR
    rw [hfun]
    exact hser

/-- P4, integer size: if `N` is NB(k, μ) and `S` given `N = n` is
Binomial(n, p), then `S` is NB(k, pμ). The mass of `S = s` is the sum over `n`
of the mass of `N = n` times the binomial mass. -/
theorem p4_thinned_nb (k : ℕ) (hk : 1 ≤ k) (μ p : ℝ) (hμ : 0 < μ) (hp0 : 0 < p) (hp1 : p ≤ 1)
    (s : ℕ) :
    HasSum (fun n : ℕ => nbPMF k μ n * binomPMF n p s) (nbPMF k (p * μ) s) := by
  obtain ⟨K, rfl⟩ : ∃ K, k = K + 1 := ⟨k - 1, by omega⟩
  have hK : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) := by positivity
  have h := thinned_nb_series K s ((K + 1 : ℕ) : ℝ) μ p hK hμ hp0 hp1
  unfold nbPMF
  have e1 : ∀ n : ℕ, n + (K + 1) - 1 = n + K := fun n => by omega
  have e2 : K + 1 - 1 = K := by omega
  simp only [e1, e2]
  exact h

/-- P4, the planning case: the benign count NB(5, 40) sampled at `p = 1/4` is
NB(5, 10). -/
theorem p4_planning_case (s : ℕ) :
    HasSum (fun n : ℕ => nbPMF 5 40 n * binomPMF n (1 / 4) s) (nbPMF 5 10 s) := by
  have h := p4_thinned_nb 5 (by norm_num) 40 (1 / 4) (by norm_num) (by norm_num) (by norm_num) s
  have h10 : (1 / 4 : ℝ) * 40 = 10 := by norm_num
  rw [h10] at h
  exact h

/-- P4, the success probabilities of the planning case: `q = 1/9` for mean 40
and `q = 1/3` for mean 10, with size 5. -/
theorem p4_planning_q :
    ((5 : ℕ) : ℝ) / (((5 : ℕ) : ℝ) + 40) = 1 / 9 ∧
      ((5 : ℕ) : ℝ) / (((5 : ℕ) : ℝ) + 10) = 1 / 3 := by
  norm_num

/-! ## P5. A thinned Poisson is Poisson, and the two selected parts are independent -/

/-- Poisson mass with mean `lam`. -/
noncomputable def poissonPMF (lam : ℝ) (n : ℕ) : ℝ :=
  Real.exp (-lam) * lam ^ n / (n.factorial : ℝ)

/-- The Poisson masses add up to one. -/
theorem poissonPMF_hasSum_one (lam : ℝ) : HasSum (poissonPMF lam) 1 := by
  have h := (real_exp_hasSum lam).mul_left (Real.exp (-lam))
  rw [← Real.exp_add, neg_add_cancel, Real.exp_zero] at h
  have hfun : poissonPMF lam = fun n : ℕ => Real.exp (-lam) * (lam ^ n / (n.factorial : ℝ)) := by
    funext n
    unfold poissonPMF
    ring
  rw [hfun]
  exact h

/-- P5, thinning: if `A` is Poisson(λ) and `S_A` given `A = a` is
Binomial(a, p), then `S_A` is Poisson(pλ). -/
theorem p5_thinned_poisson (lam p : ℝ) (s : ℕ) :
    HasSum (fun a : ℕ => poissonPMF lam a * binomPMF a p s) (poissonPMF (p * lam) s) := by
  have hser := (real_exp_hasSum (lam * (1 - p))).mul_left
    (Real.exp (-lam) * (p * lam) ^ s / (s.factorial : ℝ))
  have hval : Real.exp (-lam) * (p * lam) ^ s / (s.factorial : ℝ) * Real.exp (lam * (1 - p))
      = poissonPMF (p * lam) s := by
    unfold poissonPMF
    have hexp : Real.exp (-(p * lam)) = Real.exp (-lam) * Real.exp (lam * (1 - p)) := by
      rw [← Real.exp_add]
      congr 1
      ring
    rw [hexp]
    ring
  rw [hval] at hser
  refine hasSum_of_shift _ s _ ?_ ?_
  · intro n hn
    simp [binomPMF, Nat.choose_eq_zero_of_lt hn]
  · have hfun : (fun m : ℕ => poissonPMF lam (m + s) * binomPMF (m + s) p s)
        = fun m : ℕ => Real.exp (-lam) * (p * lam) ^ s / (s.factorial : ℝ)
            * ((lam * (1 - p)) ^ m / (m.factorial : ℝ)) := by
      funext m
      have hfac : (((m + s).choose s : ℝ)) * (m.factorial : ℝ) * (s.factorial : ℝ)
          = ((m + s).factorial : ℝ) := by
        exact_mod_cast Nat.add_choose_mul_factorial_mul_factorial m s
      have hm : (m.factorial : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero m)
      have hs : (s.factorial : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero s)
      have hms : ((m + s).factorial : ℝ) ≠ 0 :=
        Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero (m + s))
      unfold poissonPMF binomPMF
      rw [Nat.add_sub_cancel, pow_add, mul_pow, mul_pow]
      field_simp
      linear_combination (lam ^ m * lam ^ s * p ^ s * (1 - p) ^ m) * hfac
    rw [hfun]
    exact hser

/-- A sum over the sets of selected packets of two groups is a double sum over
the selected sets of each group. -/
theorem sum_finset_sum_type {α β : Type*} [Fintype α] [Fintype β] [DecidableEq α]
    [DecidableEq β] (F : Finset (α ⊕ β) → ℝ) :
    ∑ T : Finset (α ⊕ β), F T = ∑ T₁ : Finset α, ∑ T₂ : Finset β, F (T₁.disjSum T₂) := by
  let e : Finset α × Finset β ≃ Finset (α ⊕ β) :=
    { toFun := fun P => P.1.disjSum P.2
      invFun := fun T => (T.toLeft, T.toRight)
      left_inv := fun P => by simp
      right_inv := fun T => Finset.toLeft_disjSum_toRight }
  rw [← Fintype.sum_prod_type' (f := fun (T₁ : Finset α) (T₂ : Finset β) => F (T₁.disjSum T₂))]
  exact (Fintype.sum_equiv e _ _ (fun P => rfl)).symm

/-- The selection weight of two groups of packets is the product of the
weights of the two groups. -/
theorem selWeight_disjSum {α β : Type*} [Fintype α] [Fintype β] [DecidableEq α]
    [DecidableEq β] (p : ℝ) (T₁ : Finset α) (T₂ : Finset β) :
    selWeight p (T₁.disjSum T₂) = selWeight p T₁ * selWeight p T₂ := by
  unfold selWeight
  rw [Fintype.prod_sum_type]
  simp only [Finset.inl_mem_disjSum, Finset.inr_mem_disjSum]

/-- P5: the number selected from the `B + A` packets of two groups is
`S_B + S_A`, the numbers selected from each group. -/
theorem p5_selected_total {α β : Type*} (T : Finset (α ⊕ β)) :
    T.card = T.toLeft.card + T.toRight.card :=
  Finset.card_toLeft_add_card_toRight.symm

/-- P5, independence given the two counts: for packets selected independently,
the expectation of a product of a function of `S_B` and a function of `S_A` is
the product of the two binomial expectations. -/
theorem p5_two_groups_independent {α β : Type*} [Fintype α] [Fintype β] [DecidableEq α]
    [DecidableEq β] (p : ℝ) (g h : ℕ → ℝ) :
    ∑ T : Finset (α ⊕ β), selWeight p T * (g T.toLeft.card * h T.toRight.card)
      = (∑ s ∈ Finset.range (Fintype.card α + 1), binomPMF (Fintype.card α) p s * g s)
        * (∑ t ∈ Finset.range (Fintype.card β + 1), binomPMF (Fintype.card β) p t * h t) := by
  rw [sum_finset_sum_type, ← count_law, ← count_law, Finset.sum_mul_sum]
  refine Finset.sum_congr rfl fun T₁ _ => ?_
  refine Finset.sum_congr rfl fun T₂ _ => ?_
  rw [selWeight_disjSum, Finset.toLeft_disjSum, Finset.toRight_disjSum]
  ring

/-- The binomial mass as the expectation of a point indicator. -/
theorem binomPMF_point (n : ℕ) (p : ℝ) (i : ℕ) :
    ∑ s ∈ Finset.range (n + 1), binomPMF n p s * (if s = i then 1 else 0) = binomPMF n p i := by
  simp only [mul_ite, mul_one, mul_zero, Finset.sum_ite_eq', Finset.mem_range]
  split_ifs with hi
  · rfl
  · have hlt : n < i := by omega
    simp [binomPMF, Nat.choose_eq_zero_of_lt hlt]

/-- P5, joint mass given the two counts: `S_B = i` and `S_A = j` together have
the product of the two binomial masses. -/
theorem p5_two_groups_joint_mass {α β : Type*} [Fintype α] [Fintype β] [DecidableEq α]
    [DecidableEq β] (p : ℝ) (i j : ℕ) :
    ∑ T : Finset (α ⊕ β),
        selWeight p T * (if T.toLeft.card = i ∧ T.toRight.card = j then 1 else 0)
      = binomPMF (Fintype.card α) p i * binomPMF (Fintype.card β) p j := by
  have h := p5_two_groups_independent (α := α) (β := β) p (fun s => if s = i then 1 else 0)
    (fun t => if t = j then 1 else 0)
  rw [binomPMF_point, binomPMF_point] at h
  rw [← h]
  refine Finset.sum_congr rfl fun T _ => ?_
  by_cases h1 : T.toLeft.card = i <;> by_cases h2 : T.toRight.card = j <;> simp [h1, h2]

/-- P5, independence of the selected counts: let `B` and `A` be independent
counts with masses `fB` and `fA`, with packets selected independently, and let
`PB` and `PA` be the marginal masses of `S_B = i` and `S_A = j`. Then the
joint mass of `S_B = i` and `S_A = j`, summed first over `a` and then over
`b`, is the product `PB · PA`. The conditional joint mass given `B = b` and
`A = a` is the product of the two binomial masses by
`p5_two_groups_joint_mass`. -/
theorem p5_selected_counts_independent (fB fA : ℕ → ℝ) (p : ℝ) (i j : ℕ) (PB PA : ℝ)
    (hB : HasSum (fun b : ℕ => fB b * binomPMF b p i) PB)
    (hA : HasSum (fun a : ℕ => fA a * binomPMF a p j) PA) :
    (∀ b : ℕ, HasSum (fun a : ℕ => fB b * fA a * (binomPMF b p i * binomPMF a p j))
        (fB b * binomPMF b p i * PA)) ∧
      HasSum (fun b : ℕ => fB b * binomPMF b p i * PA) (PB * PA) := by
  refine ⟨fun b => ?_, hB.mul_right PA⟩
  have h := hA.mul_left (fB b * binomPMF b p i)
  have hfun : (fun a : ℕ => fB b * fA a * (binomPMF b p i * binomPMF a p j))
      = fun a : ℕ => fB b * binomPMF b p i * (fA a * binomPMF a p j) := by
    funext a
    ring
  rw [hfun]
  exact h

/-! ## P6. Distinct source hosts under selection -/

/-- P6 (a): a host is not seen after selection, that is, none of its packets
is selected, with probability `(1 − p)ᵏ`, where `k` is its packet count. -/
theorem p6a_host_unseen {ι H : Type*} [Fintype ι] [DecidableEq ι] [DecidableEq H] (p : ℝ)
    (host : ι → H) (h : H) :
    ∑ T : Finset ι, selWeight p T * (if h ∈ T.image host then 0 else 1)
      = (1 - p) ^ (Finset.univ.filter fun i => host i = h).card := by
  rw [← prob_none_selected p (Finset.univ.filter fun i => host i = h)]
  refine Finset.sum_congr rfl fun T _ => ?_
  congr 1
  by_cases hmem : h ∈ T.image host
  · have hnd : ¬ Disjoint (Finset.univ.filter fun i => host i = h) T := by
      rw [Finset.not_disjoint_iff]
      obtain ⟨i, hiT, hih⟩ := Finset.mem_image.mp hmem
      exact ⟨i, by simp [hih], hiT⟩
    rw [ite_eq_left hmem, ite_eq_right hnd]
  · have hd : Disjoint (Finset.univ.filter fun i => host i = h) T := by
      rw [Finset.disjoint_left]
      intro i hi hiT
      rw [Finset.mem_filter] at hi
      exact hmem (Finset.mem_image.mpr ⟨i, hiT, hi.2⟩)
    rw [ite_eq_right hmem, ite_eq_left hd]

/-- P6 (a) at `p = 1/4`: the probability is `(3/4)ᵏ`. -/
theorem p6a_quarter (k : ℕ) : (1 - (1 / 4 : ℝ)) ^ k = (3 / 4) ^ k := by
  norm_num

/-- P6 (b): the expected number of distinct hosts seen after selection is
`Σ_s (1 − (1 − p)^(k_s))`, where `k_s` is the packet count of host `s`. -/
theorem p6b_expected_distinct {ι H : Type*} [Fintype ι] [DecidableEq ι] [Fintype H]
    [DecidableEq H] (p : ℝ) (host : ι → H) :
    ∑ T : Finset ι, selWeight p T * ((T.image host).card : ℝ)
      = ∑ h : H, (1 - (1 - p) ^ (Finset.univ.filter fun i => host i = h).card) := by
  have hcard : ∀ T : Finset ι, ((T.image host).card : ℝ)
      = ∑ h : H, (1 - (if h ∈ T.image host then (0 : ℝ) else 1)) := by
    intro T
    have hterm : ∀ h : H, (1 - (if h ∈ T.image host then (0 : ℝ) else 1))
        = if h ∈ T.image host then 1 else 0 := by
      intro h
      split_ifs <;> ring
    simp_rw [hterm]
    rw [Finset.sum_boole]
    congr 2
    ext h
    simp
  simp_rw [hcard, Finset.mul_sum]
  rw [Finset.sum_comm]
  refine Finset.sum_congr rfl fun h _ => ?_
  have h1 := p6a_host_unseen p host h
  have h0 := selWeight_sum_one (ι := ι) p
  calc ∑ T : Finset ι, selWeight p T * (1 - (if h ∈ T.image host then (0 : ℝ) else 1))
      = ∑ T : Finset ι, selWeight p T
          - ∑ T : Finset ι, selWeight p T * (if h ∈ T.image host then 0 else 1) := by
        rw [← Finset.sum_sub_distrib]
        exact Finset.sum_congr rfl fun T _ => by ring
    _ = 1 - (1 - p) ^ (Finset.univ.filter fun i => host i = h).card := by rw [h0, h1]

/-- P6 (b), bound: for `p ≤ 1` the expected number of distinct hosts seen is
at most the number of hosts with at least one packet. -/
theorem p6b_expected_distinct_le {H : Type*} [Fintype H] (p : ℝ) (hp1 : p ≤ 1) (k : H → ℕ) :
    ∑ h : H, (1 - (1 - p) ^ k h) ≤ ((Finset.univ.filter fun h => 1 ≤ k h).card : ℝ) := by
  rw [← Finset.sum_boole]
  refine Finset.sum_le_sum fun h _ => ?_
  have hq : (0 : ℝ) ≤ 1 - p := by linarith
  by_cases hk : 1 ≤ k h
  · rw [ite_eq_left hk]
    have := pow_nonneg hq (k h)
    linarith
  · have hk0 : k h = 0 := by omega
    rw [ite_eq_right hk, hk0, pow_zero, sub_self]

/-- P6 (b), strictness: for `p < 1` and at least one host with a packet, the
expected number of distinct hosts seen is strictly below the true number. -/
theorem p6b_expected_distinct_lt {H : Type*} [Fintype H] (p : ℝ) (hp1 : p < 1) (k : H → ℕ)
    (hex : ∃ h, 1 ≤ k h) :
    ∑ h : H, (1 - (1 - p) ^ k h) < ((Finset.univ.filter fun h => 1 ≤ k h).card : ℝ) := by
  rw [← Finset.sum_boole]
  have hq : (0 : ℝ) < 1 - p := by linarith
  obtain ⟨h0, hh0⟩ := hex
  refine Finset.sum_lt_sum (fun h _ => ?_) ⟨h0, Finset.mem_univ h0, ?_⟩
  · by_cases hk : 1 ≤ k h
    · rw [ite_eq_left hk]
      have := pow_nonneg hq.le (k h)
      linarith
    · have hk0 : k h = 0 := by omega
      rw [ite_eq_right hk, hk0, pow_zero, sub_self]
  · rw [ite_eq_left hh0]
    have := pow_pos hq (k h0)
    linarith

/-- P6 (c): for `p ≠ 1` no constant factor corrects the count. With one host,
one packet needs `c p = 1` and two packets need `c p (2 − p) = 1`. -/
theorem p6c_no_constant_factor {H : Type*} [Fintype H] [DecidableEq H] [Nonempty H] (p : ℝ)
    (hp : p ≠ 1) :
    ¬ ∃ c : ℝ, ∀ k : H → ℕ,
      c * ∑ h : H, (1 - (1 - p) ^ k h) = ((Finset.univ.filter fun h => 1 ≤ k h).card : ℝ) := by
  rintro ⟨c, hc⟩
  obtain ⟨h0⟩ := ‹Nonempty H›
  have hsum : ∀ m : ℕ, 1 ≤ m →
      c * (1 - (1 - p) ^ m) = 1 := by
    intro m hm
    have h := hc (fun h => if h = h0 then m else 0)
    have hs : ∑ h : H, (1 - (1 - p) ^ (if h = h0 then m else 0)) = 1 - (1 - p) ^ m := by
      rw [Finset.sum_eq_single h0]
      · simp
      · intro h _ hne
        simp [hne]
      · intro hne
        exact absurd (Finset.mem_univ h0) hne
    have hf : (Finset.univ.filter fun h => 1 ≤ (if h = h0 then m else 0)) = {h0} := by
      ext h
      by_cases hh : h = h0
      · simp [hh, hm]
      · simp [hh]
    rw [hs, hf, Finset.card_singleton, Nat.cast_one] at h
    exact h
  have h1 := hsum 1 le_rfl
  have h2 := hsum 2 (by norm_num)
  have hcp : c * p = 1 := by linarith
  have hprod : c * p * (2 - p) = 1 := by linarith
  rw [hcp] at hprod
  exact hp (by linarith)

/-- P6 (c), the excluded boundary: at `p = 1` every packet is selected and the
constant `c = 1` is exact. The statement of P6 (c) therefore needs `p < 1`. -/
theorem p6c_constant_at_one {H : Type*} [Fintype H] (k : H → ℕ) :
    (1 : ℝ) * ∑ h : H, (1 - (1 - (1 : ℝ)) ^ k h)
      = ((Finset.univ.filter fun h => 1 ≤ k h).card : ℝ) := by
  rw [one_mul, ← Finset.sum_boole]
  refine Finset.sum_congr rfl fun h _ => ?_
  by_cases hk : 1 ≤ k h
  · have hk0 : k h ≠ 0 := by omega
    rw [ite_eq_left hk, sub_self, zero_pow hk0, sub_zero]
  · have hk0 : k h = 0 := by omega
    rw [ite_eq_right hk, hk0, pow_zero, sub_self]

/-- P6 (c) at `p = 1/4`: `n ≥ 1` hosts with one packet each need `c = 4`, and
`n` hosts with two packets each need `c = 16/7`. -/
theorem p6c_quarter_instances (n : ℕ) (hn : 0 < n) (c : ℝ) :
    (c * ((n : ℝ) * (1 - (1 - (1 / 4 : ℝ)) ^ 1)) = n ↔ c = 4) ∧
    (c * ((n : ℝ) * (1 - (1 - (1 / 4 : ℝ)) ^ 2)) = n ↔ c = 16 / 7) := by
  have hn' : (0 : ℝ) < n := by exact_mod_cast hn
  constructor
  · constructor
    · intro h
      have h4 : (n : ℝ) * (c / 4 - 1) = 0 := by linarith
      rcases mul_eq_zero.mp h4 with h0 | h0
      · exact absurd h0 hn'.ne'
      · linarith
    · intro h
      rw [h]
      ring
  · constructor
    · intro h
      have h4 : (n : ℝ) * (c * 7 / 16 - 1) = 0 := by linarith
      rcases mul_eq_zero.mp h4 with h0 | h0
      · exact absurd h0 hn'.ne'
      · linarith
    · intro h
      rw [h]
      ring

/-- P6 (d), one source: if a source emits a Poisson(λ) number of packets, it
is seen after selection, that is, at least one of its packets is selected,
with probability `1 − e^(−pλ)`. With `p = 1` this is the probability
`1 − e^(−λ)` that it emits at least one packet. -/
theorem p6d_source_seen (lam p : ℝ) :
    HasSum (fun a : ℕ => poissonPMF lam a * (1 - (1 - p) ^ a)) (1 - Real.exp (-(p * lam))) := by
  have h1 := poissonPMF_hasSum_one lam
  have h2 := p5_thinned_poisson lam p 0
  have hval : poissonPMF (p * lam) 0 = Real.exp (-(p * lam)) := by
    simp [poissonPMF]
  rw [hval] at h2
  have h := h1.sub h2
  have hfun : (fun a : ℕ => poissonPMF lam a * (1 - (1 - p) ^ a))
      = fun a : ℕ => poissonPMF lam a - poissonPMF lam a * binomPMF a p 0 := by
    funext a
    simp only [binomPMF, Nat.choose_zero_right, Nat.cast_one, pow_zero, Nat.sub_zero]
    ring
  rw [hfun]
  exact h

/-- P6 (d): with `n` sources that each emit a Poisson(Λ/n) number of packets,
the sum over the sources of the probability of being seen is
`n (1 − e^(−pΛ/n))` after selection. -/
theorem p6d_expected_distinct (n : ℕ) (Lam p : ℝ) :
    HasSum (fun a : ℕ => ∑ _j : Fin n, poissonPMF (Lam / n) a * (1 - (1 - p) ^ a))
      ((n : ℝ) * (1 - Real.exp (-(p * Lam / n)))) := by
  have h := hasSum_sum (s := (Finset.univ : Finset (Fin n)))
    (f := fun (_ : Fin n) (a : ℕ) => poissonPMF (Lam / n) a * (1 - (1 - p) ^ a))
    (fun _ _ => p6d_source_seen (Lam / n) p)
  simp only [Finset.sum_const, Finset.card_univ, Fintype.card_fin, nsmul_eq_mul] at h
  have hval : p * (Lam / (n : ℝ)) = p * Lam / (n : ℝ) := by ring
  rw [hval] at h
  simpa only [Finset.sum_const, Finset.card_univ, Fintype.card_fin, nsmul_eq_mul] using h

/-- P6 (d), before selection: the same sum is `n (1 − e^(−Λ/n))`, where a
source counts when it emits at least one packet. -/
theorem p6d_expected_distinct_before (n : ℕ) (Lam : ℝ) :
    HasSum (fun a : ℕ => ∑ _j : Fin n, poissonPMF (Lam / n) a * (if 1 ≤ a then 1 else 0))
      ((n : ℝ) * (1 - Real.exp (-(Lam / n)))) := by
  have h := p6d_expected_distinct n Lam 1
  have hfun : (fun a : ℕ => ∑ _j : Fin n, poissonPMF (Lam / n) a * (if 1 ≤ a then (1 : ℝ) else 0))
      = fun a : ℕ => ∑ _j : Fin n, poissonPMF (Lam / n) a * (1 - (1 - (1 : ℝ)) ^ a) := by
    funext a
    refine Finset.sum_congr rfl fun _ _ => ?_
    by_cases ha : 1 ≤ a
    · have ha0 : a ≠ 0 := by omega
      rw [ite_eq_left ha, sub_self, zero_pow ha0, sub_zero]
    · have ha0 : a = 0 := by omega
      rw [ite_eq_right ha, ha0, pow_zero, sub_self]
  rw [hfun]
  rw [one_mul] at h
  exact h

/-- P6 (d), disjoint parts: if the hosts of two sets of packets (benign
sources and bots) are disjoint, the distinct count of the union is the sum of
the two distinct counts. -/
theorem p6d_disjoint_sources {ι H : Type*} [DecidableEq ι] [DecidableEq H] (host : ι → H)
    (T₁ T₂ : Finset ι) (hdisj : Disjoint (T₁.image host) (T₂.image host)) :
    ((T₁ ∪ T₂).image host).card = (T₁.image host).card + (T₂.image host).card := by
  rw [Finset.image_union, Finset.card_union_of_disjoint hdisj]

/-! ## P7. The rank-rule threshold -/

/-- P7: for `n ≥ 1` the rank `r = ⌈0.99 n⌉` satisfies `1 ≤ r ≤ n` and
`n − r ≤ n/100`. -/
theorem p7_rank_bounds (n : ℕ) (hn : 1 ≤ n) :
    1 ≤ ⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ ∧ ⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ ≤ n ∧
      (n : ℝ) - (⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ : ℝ) ≤ (n : ℝ) / 100 := by
  have hn' : (1 : ℝ) ≤ n := by exact_mod_cast hn
  refine ⟨?_, ?_, ?_⟩
  · exact Nat.ceil_pos.mpr (by linarith)
  · exact Nat.ceil_le.mpr (by linarith)
  · have h := Nat.le_ceil ((99 / 100 : ℝ) * (n : ℝ))
    linarith

/-- P7 (a), counting part: if `t` is the `r`-th smallest of `n` scores, at
most `n − r` scores exceed `t` (`Foundations.order_statistic_exceed_count_le`). -/
theorem p7a_exceed_count_le {n : ℕ} (x : Fin n → ℝ) (r : ℕ) (hr1 : 1 ≤ r) (hrn : r ≤ n) :
    (Finset.univ.filter fun i => x (Tuple.sort x ⟨r - 1, by omega⟩) < x i).card ≤ n - r := by
  have h := Foundations.order_statistic_exceed_count_le x ⟨r - 1, by omega⟩
  have hidx : n - (r - 1 + 1) = n - r := by omega
  simp only [hidx] at h
  exact h

/-- P7 (a): with `r = ⌈0.99 n⌉` and `t` the `r`-th smallest score, the number
of scores above `t` is at most `n/100`, so the strict rule flags at most 1% of
the calibration pool. -/
theorem p7a_rank_rule {n : ℕ} (hn : 1 ≤ n) (x : Fin n → ℝ)
    (hr : ⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ - 1 < n) :
    ((Finset.univ.filter fun i =>
        x (Tuple.sort x ⟨⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ - 1, hr⟩) < x i).card : ℝ)
      ≤ (n : ℝ) / 100 := by
  obtain ⟨h1, h2, h3⟩ := p7_rank_bounds n hn
  have hc := p7a_exceed_count_le x _ h1 h2
  have hreal : ((Finset.univ.filter fun i =>
      x (Tuple.sort x ⟨⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ - 1, hr⟩) < x i).card : ℝ)
      ≤ ((n - ⌈(99 / 100 : ℝ) * (n : ℝ)⌉₊ : ℕ) : ℝ) := by
    exact_mod_cast hc
  rw [Nat.cast_sub h2] at hreal
  linarith

/-- The number of entries of `y` strictly below entry `j`. -/
noncomputable def belowCount {m : ℕ} (y : Fin m → ℝ) (j : Fin m) : ℕ :=
  (Finset.univ.filter fun i => y i < y j).card

/-- A value `v` exceeds the `r`-th smallest of `n` scores exactly when at
least `r` scores are strictly below `v`
(`Foundations.order_statistic_mem_lower_iff`). -/
theorem p7b_exceeds_iff {n : ℕ} (x : Fin n → ℝ) (r : ℕ) (hr1 : 1 ≤ r) (hrn : r ≤ n) (v : ℝ) :
    x (Tuple.sort x ⟨r - 1, by omega⟩) < v ↔ r ≤ (Finset.univ.filter fun i => x i < v).card := by
  have h := Foundations.order_statistic_mem_lower_iff x (fun t => t < v)
    (fun a ha b hb => lt_of_le_of_lt hb ha) ⟨r - 1, by omega⟩
  have hidx : r - 1 + 1 = r := by omega
  simp only [hidx] at h
  exact h

/-- Among `m` values, at most `m − r` have at least `r` values strictly below
them. Ties are allowed. -/
theorem p7b_rank_count_le {m : ℕ} (y : Fin m → ℝ) (r : ℕ) :
    (Finset.univ.filter fun j => r ≤ belowCount y j).card ≤ m - r := by
  by_cases hne : (Finset.univ.filter fun j => r ≤ belowCount y j).Nonempty
  · obtain ⟨j0, hj0, hEq⟩ := Finset.exists_mem_eq_inf' hne y
    have hmin : ∀ b ∈ Finset.univ.filter fun j => r ≤ belowCount y j, y j0 ≤ y b := by
      intro b hb
      rw [← hEq]
      exact Finset.inf'_le y hb
    have hsub : (Finset.univ.filter fun i => y i < y j0)
        ⊆ (Finset.univ.filter fun j => r ≤ belowCount y j)ᶜ := by
      intro i hi
      rw [Finset.mem_filter] at hi
      rw [Finset.mem_compl]
      intro hiJ
      exact absurd (hmin i hiJ) (not_le.mpr hi.2)
    have hcard := Finset.card_le_card hsub
    rw [Finset.card_compl, Fintype.card_fin] at hcard
    have hr : r ≤ belowCount y j0 := (Finset.mem_filter.mp hj0).2
    have hJm := Finset.card_le_univ (Finset.univ.filter fun j => r ≤ belowCount y j)
    rw [Fintype.card_fin] at hJm
    unfold belowCount at hr
    omega
  · rw [Finset.not_nonempty_iff_eq_empty] at hne
    rw [hne, Finset.card_empty]
    exact Nat.zero_le _

/-- Among `m` distinct values, exactly `m − r` have at least `r` values
strictly below them. -/
theorem p7b_rank_count_eq {m : ℕ} (y : Fin m → ℝ) (hy : Function.Injective y) (r : ℕ) :
    (Finset.univ.filter fun j => r ≤ belowCount y j).card = m - r := by
  refine le_antisymm (p7b_rank_count_le y r) ?_
  have hlt : ∀ a b : Fin m, y a < y b → belowCount y a < belowCount y b := by
    intro a b hab
    unfold belowCount
    refine Finset.card_lt_card ?_
    have hsub : (Finset.univ.filter fun i => y i < y a)
        ⊆ (Finset.univ.filter fun i => y i < y b) := by
      intro i hi
      rw [Finset.mem_filter] at hi ⊢
      exact ⟨hi.1, lt_trans hi.2 hab⟩
    rw [Finset.ssubset_iff_of_subset hsub]
    exact ⟨a, by simp [hab], by simp⟩
  have hinj : Set.InjOn (belowCount y)
      (↑(Finset.univ.filter fun j => ¬ r ≤ belowCount y j) : Set (Fin m)) := by
    intro a _ b _ hab
    by_contra hne
    have hyne : y a ≠ y b := fun h => hne (hy h)
    rcases lt_or_gt_of_ne hyne with h | h
    · have := hlt a b h
      omega
    · have := hlt b a h
      omega
  have hmaps : Set.MapsTo (belowCount y)
      (↑(Finset.univ.filter fun j => ¬ r ≤ belowCount y j) : Set (Fin m))
      (↑(Finset.range r) : Set ℕ) := by
    intro a ha
    rw [Finset.mem_coe, Finset.mem_filter] at ha
    rw [Finset.mem_coe, Finset.mem_range]
    omega
  have hcomp := Finset.card_le_card_of_injOn (belowCount y) hmaps hinj
  rw [Finset.card_range] at hcomp
  have htot := Finset.card_filter_add_card_filter_not (s := (Finset.univ : Finset (Fin m)))
    (fun j => r ≤ belowCount y j)
  rw [Finset.card_univ, Fintype.card_fin] at htot
  omega

/-- The below-count of the last entry counts the first `n` entries only. -/
theorem p7b_last_belowCount {n : ℕ} (y : Fin (n + 1) → ℝ) :
    belowCount y (Fin.last n)
      = (Finset.univ.filter fun i : Fin n => y (Fin.castSucc i) < y (Fin.last n)).card := by
  unfold belowCount
  rw [Finset.card_filter, Finset.card_filter, Fin.sum_univ_castSucc]
  simp

/-- Reordering the entries moves the below-counts with them. -/
theorem belowCount_comp_perm {m : ℕ} (y : Fin m → ℝ) (σ : Equiv.Perm (Fin m)) (j : Fin m) :
    belowCount (y ∘ σ) j = belowCount y (σ j) := by
  unfold belowCount
  rw [Finset.card_filter, Finset.card_filter]
  exact Equiv.sum_comp σ (fun i => if y i < y (σ j) then 1 else 0)

/-- The event of P7 (b): the new value `y (last)` exceeds the `r`-th smallest
of the first `n` values exactly when at least `r` values lie strictly below
it. -/
theorem p7b_event_iff {n : ℕ} (y : Fin (n + 1) → ℝ) (r : ℕ) (hr1 : 1 ≤ r) (hrn : r ≤ n) :
    y (Fin.castSucc (Tuple.sort (fun i : Fin n => y (Fin.castSucc i)) ⟨r - 1, by omega⟩))
        < y (Fin.last n)
      ↔ r ≤ belowCount y (Fin.last n) := by
  rw [p7b_last_belowCount]
  exact p7b_exceeds_iff (fun i : Fin n => y (Fin.castSucc i)) r hr1 hrn (y (Fin.last n))

/-- Symmetry step of P7 (b). For an exchangeable vector on a finite sample
space, `n + 1` times the probability that the last value has at least `r`
values below it is the expected number of positions with that property. -/
theorem p7b_symmetry {Ω : Type*} [Fintype Ω] {n : ℕ} (π : Ω → ℝ) (X : Ω → Fin (n + 1) → ℝ)
    (r : ℕ)
    (hex : ∀ (σ : Equiv.Perm (Fin (n + 1))) (g : (Fin (n + 1) → ℝ) → ℝ),
      ∑ ω, π ω * g (X ω ∘ σ) = ∑ ω, π ω * g (X ω)) :
    ((n : ℝ) + 1) * ∑ ω, π ω * (if r ≤ belowCount (X ω) (Fin.last n) then 1 else 0)
      = ∑ ω, π ω * ((Finset.univ.filter fun j => r ≤ belowCount (X ω) j).card : ℝ) := by
  have hj : ∀ j : Fin (n + 1),
      ∑ ω, π ω * (if r ≤ belowCount (X ω) j then (1 : ℝ) else 0)
        = ∑ ω, π ω * (if r ≤ belowCount (X ω) (Fin.last n) then 1 else 0) := by
    intro j
    have h := hex (Equiv.swap j (Fin.last n))
      (fun y => if r ≤ belowCount y (Fin.last n) then 1 else 0)
    rw [← h]
    refine Finset.sum_congr rfl fun ω _ => ?_
    rw [belowCount_comp_perm, Equiv.swap_apply_right]
  symm
  calc ∑ ω, π ω * ((Finset.univ.filter fun j => r ≤ belowCount (X ω) j).card : ℝ)
      = ∑ ω, ∑ j : Fin (n + 1), π ω * (if r ≤ belowCount (X ω) j then (1 : ℝ) else 0) := by
        refine Finset.sum_congr rfl fun ω _ => ?_
        rw [← Finset.mul_sum, Finset.sum_boole]
    _ = ∑ j : Fin (n + 1), ∑ ω, π ω * (if r ≤ belowCount (X ω) j then (1 : ℝ) else 0) :=
        Finset.sum_comm
    _ = ∑ _j : Fin (n + 1), ∑ ω, π ω * (if r ≤ belowCount (X ω) (Fin.last n) then 1 else 0) :=
        Finset.sum_congr rfl fun j _ => hj j
    _ = ((n : ℝ) + 1) * ∑ ω, π ω * (if r ≤ belowCount (X ω) (Fin.last n) then 1 else 0) := by
        rw [Finset.sum_const, Finset.card_univ, Fintype.card_fin, nsmul_eq_mul]
        push_cast
        ring

/-- P7 (b), with ties: for an exchangeable vector `X₁, …, X₍ₙ₊₁₎` on a finite
sample space and `t` the `r`-th smallest of `X₁, …, Xₙ`, the strict rule gives
`P(X₍ₙ₊₁₎ > t) ≤ (n − r + 1)/(n + 1)`. -/
theorem p7b_exchangeable_le {Ω : Type*} [Fintype Ω] {n : ℕ} (π : Ω → ℝ)
    (X : Ω → Fin (n + 1) → ℝ) (r : ℕ) (hr1 : 1 ≤ r) (hrn : r ≤ n)
    (hπ0 : ∀ ω, 0 ≤ π ω) (hπ : ∑ ω, π ω = 1)
    (hex : ∀ (σ : Equiv.Perm (Fin (n + 1))) (g : (Fin (n + 1) → ℝ) → ℝ),
      ∑ ω, π ω * g (X ω ∘ σ) = ∑ ω, π ω * g (X ω)) :
    ∑ ω, π ω * (if X ω (Fin.castSucc
        (Tuple.sort (fun i : Fin n => X ω (Fin.castSucc i)) ⟨r - 1, by omega⟩))
          < X ω (Fin.last n) then 1 else 0)
      ≤ ((n : ℝ) - (r : ℝ) + 1) / ((n : ℝ) + 1) := by
  have hev : ∀ ω, (if X ω (Fin.castSucc
        (Tuple.sort (fun i : Fin n => X ω (Fin.castSucc i)) ⟨r - 1, by omega⟩))
          < X ω (Fin.last n) then (1 : ℝ) else 0)
      = (if r ≤ belowCount (X ω) (Fin.last n) then 1 else 0) :=
    fun ω => if_congr (p7b_event_iff (X ω) r hr1 hrn) rfl rfl
  simp_rw [hev]
  have hsym := p7b_symmetry π X r hex
  have hbound : ∑ ω, π ω * ((Finset.univ.filter fun j => r ≤ belowCount (X ω) j).card : ℝ)
      ≤ ∑ ω, π ω * ((n : ℝ) - (r : ℝ) + 1) := by
    refine Finset.sum_le_sum fun ω _ => mul_le_mul_of_nonneg_left ?_ (hπ0 ω)
    have hc := p7b_rank_count_le (X ω) r
    have hcast : ((Finset.univ.filter fun j => r ≤ belowCount (X ω) j).card : ℝ)
        ≤ ((n + 1 - r : ℕ) : ℝ) := by exact_mod_cast hc
    rw [Nat.cast_sub (by omega)] at hcast
    push_cast at hcast
    linarith
  rw [← Finset.sum_mul, hπ, one_mul] at hbound
  have hpos : (0 : ℝ) < (n : ℝ) + 1 := by positivity
  rw [le_div_iff₀ hpos]
  linarith

/-- P7 (b): if in addition the values are distinct with probability one, then
`P(X₍ₙ₊₁₎ > t) = (n − r + 1)/(n + 1)`. -/
theorem p7b_exchangeable_eq {Ω : Type*} [Fintype Ω] {n : ℕ} (π : Ω → ℝ)
    (X : Ω → Fin (n + 1) → ℝ) (r : ℕ) (hr1 : 1 ≤ r) (hrn : r ≤ n)
    (hπ : ∑ ω, π ω = 1)
    (hex : ∀ (σ : Equiv.Perm (Fin (n + 1))) (g : (Fin (n + 1) → ℝ) → ℝ),
      ∑ ω, π ω * g (X ω ∘ σ) = ∑ ω, π ω * g (X ω))
    (hdistinct : ∀ ω, π ω ≠ 0 → Function.Injective (X ω)) :
    ∑ ω, π ω * (if X ω (Fin.castSucc
        (Tuple.sort (fun i : Fin n => X ω (Fin.castSucc i)) ⟨r - 1, by omega⟩))
          < X ω (Fin.last n) then 1 else 0)
      = ((n : ℝ) - (r : ℝ) + 1) / ((n : ℝ) + 1) := by
  have hev : ∀ ω, (if X ω (Fin.castSucc
        (Tuple.sort (fun i : Fin n => X ω (Fin.castSucc i)) ⟨r - 1, by omega⟩))
          < X ω (Fin.last n) then (1 : ℝ) else 0)
      = (if r ≤ belowCount (X ω) (Fin.last n) then 1 else 0) :=
    fun ω => if_congr (p7b_event_iff (X ω) r hr1 hrn) rfl rfl
  simp_rw [hev]
  have hsym := p7b_symmetry π X r hex
  have hcount : ∑ ω, π ω * ((Finset.univ.filter fun j => r ≤ belowCount (X ω) j).card : ℝ)
      = ∑ ω, π ω * ((n : ℝ) - (r : ℝ) + 1) := by
    refine Finset.sum_congr rfl fun ω _ => ?_
    by_cases h0 : π ω = 0
    · rw [h0, zero_mul, zero_mul]
    · have hc := p7b_rank_count_eq (X ω) (hdistinct ω h0) r
      rw [hc, Nat.cast_sub (by omega)]
      push_cast
      ring
  rw [← Finset.sum_mul, hπ, one_mul] at hcount
  have hpos : (0 : ℝ) < (n : ℝ) + 1 := by positivity
  rw [eq_div_iff hpos.ne']
  linarith

/-- P7, numbers: `n = 1200` gives `r = 1188`, the 13th largest score, and
`13/1201`, which rounds to 1.08%; `n = 400` gives `r = 396`, the 5th largest,
and `5/401`, which rounds to 1.25%; `n = 300` gives `r = 297`, the 4th
largest, and `4/301`, which rounds to 1.33%. -/
theorem p7_numbers :
    (⌈(99 / 100 : ℝ) * ((1200 : ℕ) : ℝ)⌉₊ = 1188 ∧ 1200 - 1188 + 1 = 13 ∧
      (0.01075 : ℝ) ≤ 13 / 1201 ∧ (13 / 1201 : ℝ) < 0.01085) ∧
    (⌈(99 / 100 : ℝ) * ((400 : ℕ) : ℝ)⌉₊ = 396 ∧ 400 - 396 + 1 = 5 ∧
      (0.01245 : ℝ) ≤ 5 / 401 ∧ (5 / 401 : ℝ) < 0.01255) ∧
    (⌈(99 / 100 : ℝ) * ((300 : ℕ) : ℝ)⌉₊ = 297 ∧ 300 - 297 + 1 = 4 ∧
      (0.01325 : ℝ) ≤ 4 / 301 ∧ (4 / 301 : ℝ) < 0.01335) := by
  refine ⟨⟨?_, by norm_num, by norm_num, by norm_num⟩, ⟨?_, by norm_num, by norm_num, by norm_num⟩,
    ⟨?_, by norm_num, by norm_num, by norm_num⟩⟩
  · rw [Nat.ceil_eq_iff (by norm_num)]
    norm_num
  · rw [Nat.ceil_eq_iff (by norm_num)]
    norm_num
  · rw [Nat.ceil_eq_iff (by norm_num)]
    norm_num

/-! ## Moments on a finite sample space -/

/-- Expectation of `Z` on a finite sample space with weights `π`. -/
noncomputable def fmean {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (Z : Ω → ℝ) : ℝ :=
  ∑ ω, π ω * Z ω

/-- Variance of `Z`: the expectation of the squared deviation from the mean. -/
noncomputable def fvar {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (Z : Ω → ℝ) : ℝ :=
  fmean π (fun ω => (Z ω - fmean π Z) ^ 2)

/-- Covariance of `Z` and `W`. -/
noncomputable def fcov {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (Z W : Ω → ℝ) : ℝ :=
  fmean π (fun ω => (Z ω - fmean π Z) * (W ω - fmean π W))

/-- The indicator of a Boolean outcome as a real number. -/
noncomputable def boolInd (b : Bool) : ℝ := if b then 1 else 0

/-- The expectation of a constant multiple. -/
theorem fmean_const_mul {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (c : ℝ) (Z : Ω → ℝ) :
    fmean π (fun ω => c * Z ω) = c * fmean π Z := by
  unfold fmean
  rw [Finset.mul_sum]
  refine Finset.sum_congr rfl fun ω _ => ?_
  ring

/-- The expectation of a finite sum. -/
theorem fmean_sum {Ω ι : Type*} [Fintype Ω] (π : Ω → ℝ) (s : Finset ι) (Z : ι → Ω → ℝ) :
    fmean π (fun ω => ∑ i ∈ s, Z i ω) = ∑ i ∈ s, fmean π (Z i) := by
  unfold fmean
  rw [Finset.sum_comm]
  refine Finset.sum_congr rfl fun ω _ => ?_
  rw [Finset.mul_sum]

/-- The covariance of a variable with itself is its variance. -/
theorem fcov_self {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (Z : Ω → ℝ) : fcov π Z Z = fvar π Z := by
  unfold fcov fvar
  congr 1
  funext ω
  ring

/-! ## P8. Mean and variance of the paired alert difference -/

/-- P8, mean: for `X, Y ∈ {0, 1}` and `D = X − Y`,
`E[D] = P(X = 1) − P(Y = 1) = p10 − p01`. -/
theorem p8_mean {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (X Y : Ω → Bool) :
    fmean π (fun ω => boolInd (X ω) - boolInd (Y ω))
        = fmean π (fun ω => boolInd (X ω)) - fmean π (fun ω => boolInd (Y ω)) ∧
      fmean π (fun ω => boolInd (X ω) - boolInd (Y ω))
        = fmean π (fun ω => boolInd (X ω && !Y ω)) - fmean π (fun ω => boolInd (!X ω && Y ω)) := by
  unfold fmean
  constructor
  · rw [← Finset.sum_sub_distrib]
    refine Finset.sum_congr rfl fun ω _ => ?_
    ring
  · rw [← Finset.sum_sub_distrib]
    refine Finset.sum_congr rfl fun ω _ => ?_
    cases hX : X ω <;> cases hY : Y ω <;> simp [boolInd, hX, hY]

/-- P8, variance: `Var(D) = p10 + p01 − (p10 − p01)²`. -/
theorem p8_variance {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (X Y : Ω → Bool) (hπ : ∑ ω, π ω = 1) :
    fvar π (fun ω => boolInd (X ω) - boolInd (Y ω))
      = fmean π (fun ω => boolInd (X ω && !Y ω)) + fmean π (fun ω => boolInd (!X ω && Y ω))
        - (fmean π (fun ω => boolInd (X ω && !Y ω))
          - fmean π (fun ω => boolInd (!X ω && Y ω))) ^ 2 := by
  have hm := (p8_mean π X Y).2
  unfold fvar
  rw [hm]
  unfold fmean
  have hpt : ∀ (d : ℝ) (ω : Ω), π ω * ((boolInd (X ω) - boolInd (Y ω)) - d) ^ 2
      = π ω * boolInd (X ω && !Y ω) + π ω * boolInd (!X ω && Y ω)
        - 2 * d * (π ω * boolInd (X ω && !Y ω) - π ω * boolInd (!X ω && Y ω))
        + d ^ 2 * π ω := by
    intro d ω
    cases X ω <;> cases Y ω <;> simp [boolInd] <;> ring
  rw [Finset.sum_congr rfl fun ω _ => hpt _ ω, Finset.sum_add_distrib, Finset.sum_sub_distrib,
    Finset.sum_add_distrib, ← Finset.mul_sum, ← Finset.mul_sum, Finset.sum_sub_distrib, hπ]
  ring

/-! ## P9. Design effect of a cluster mean -/

/-- P9 (a): if `D₁, …, D_m` have a common variance `σ²` and every pair has
covariance `ρ σ²` (a common correlation `ρ`), then
`Var((1/m) Σ Dᵢ) = (σ²/m)(1 + (m − 1)ρ)`. -/
theorem p9a_design_effect {Ω : Type*} [Fintype Ω] {m : ℕ} (hm : 0 < m) (π : Ω → ℝ)
    (D : Fin m → Ω → ℝ) (σ2 ρ : ℝ) (hvar : ∀ i, fvar π (D i) = σ2)
    (hcov : ∀ i j, i ≠ j → fcov π (D i) (D j) = ρ * σ2) :
    fvar π (fun ω => (1 / (m : ℝ)) * ∑ i, D i ω) = (σ2 / m) * (1 + ((m : ℝ) - 1) * ρ) := by
  have hmean : fmean π (fun ω => (1 / (m : ℝ)) * ∑ i, D i ω)
      = (1 / (m : ℝ)) * ∑ i, fmean π (D i) := by
    rw [fmean_const_mul, fmean_sum]
  have hpt : ∀ ω, ((1 / (m : ℝ)) * ∑ i, D i ω - (1 / (m : ℝ)) * ∑ i, fmean π (D i)) ^ 2
      = (1 / (m : ℝ)) ^ 2
        * ∑ i, ∑ j, (D i ω - fmean π (D i)) * (D j ω - fmean π (D j)) := by
    intro ω
    rw [← mul_sub, ← Finset.sum_sub_distrib, mul_pow, sq (∑ i, (D i ω - fmean π (D i))),
      Finset.sum_mul_sum]
  have h2 : fvar π (fun ω => (1 / (m : ℝ)) * ∑ i, D i ω)
      = (1 / (m : ℝ)) ^ 2 * ∑ i, ∑ j, fcov π (D i) (D j) := by
    unfold fvar
    rw [hmean]
    simp_rw [hpt]
    rw [fmean_const_mul, fmean_sum]
    congr 1
    refine Finset.sum_congr rfl fun i _ => ?_
    rw [fmean_sum]
    rfl
  rw [h2]
  have hij : ∀ i j, fcov π (D i) (D j) = ρ * σ2 + (if i = j then σ2 - ρ * σ2 else 0) := by
    intro i j
    by_cases h : i = j
    · subst h
      rw [ite_eq_left rfl, fcov_self, hvar]
      ring
    · rw [ite_eq_right h, hcov i j h, add_zero]
  simp_rw [hij]
  simp only [Finset.sum_add_distrib, Finset.sum_const, Finset.card_univ, Fintype.card_fin,
    nsmul_eq_mul, Finset.sum_ite_eq, Finset.mem_univ, ite_true]
  have hm' : (m : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr hm.ne'
  field_simp
  ring

/-- P9 (b): let `U` take finitely many values with weights `q`, and let `D₁`
and `D₂` be independent given `U = u`, each with the conditional law `ν u` on
the values `v`. Then `Cov(D₁, D₂) = Var(E[D₁ | U])`. The sample space is the
set of triples `(u, a, b)` with weight `q u · ν u a · ν u b`. -/
theorem p9b_conditional_iid_covariance {𝒰 A : Type*} [Fintype 𝒰] [Fintype A] (q : 𝒰 → ℝ)
    (ν : 𝒰 → A → ℝ) (v : A → ℝ) (hν : ∀ u, ∑ a, ν u a = 1) :
    fcov (fun ω : 𝒰 × A × A => q ω.1 * ν ω.1 ω.2.1 * ν ω.1 ω.2.2)
        (fun ω => v ω.2.1) (fun ω => v ω.2.2)
      = fvar q (fun u => ∑ a, ν u a * v a) := by
  have hsum : ∀ F : 𝒰 × A × A → ℝ, ∑ ω, F ω = ∑ u, ∑ a, ∑ b, F (u, a, b) := by
    intro F
    rw [Fintype.sum_prod_type]
    refine Finset.sum_congr rfl fun u _ => ?_
    rw [Fintype.sum_prod_type]
  have hm1 : fmean (fun ω : 𝒰 × A × A => q ω.1 * ν ω.1 ω.2.1 * ν ω.1 ω.2.2) (fun ω => v ω.2.1)
      = fmean q (fun u => ∑ a, ν u a * v a) := by
    unfold fmean
    rw [hsum]
    refine Finset.sum_congr rfl fun u _ => ?_
    have ha : ∀ a, ∑ b, q u * ν u a * ν u b * v a = q u * (ν u a * v a) := by
      intro a
      rw [← Finset.sum_mul, ← Finset.mul_sum, hν u]
      ring
    simp_rw [ha]
    rw [← Finset.mul_sum]
  have hm2 : fmean (fun ω : 𝒰 × A × A => q ω.1 * ν ω.1 ω.2.1 * ν ω.1 ω.2.2) (fun ω => v ω.2.2)
      = fmean q (fun u => ∑ a, ν u a * v a) := by
    unfold fmean
    rw [hsum]
    refine Finset.sum_congr rfl fun u _ => ?_
    rw [Finset.sum_comm]
    have hb : ∀ b, ∑ a, q u * ν u a * ν u b * v b = q u * (ν u b * v b) := by
      intro b
      rw [← Finset.sum_mul, ← Finset.sum_mul, ← Finset.mul_sum, hν u]
      ring
    simp_rw [hb]
    rw [← Finset.mul_sum]
  unfold fcov fvar
  rw [hm1, hm2]
  generalize fmean q (fun u => ∑ a, ν u a * v a) = μ
  unfold fmean
  rw [hsum]
  refine Finset.sum_congr rfl fun u _ => ?_
  have key : ∑ a, ν u a * (v a - μ) = (∑ a, ν u a * v a) - μ := by
    simp_rw [mul_sub]
    rw [Finset.sum_sub_distrib, ← Finset.sum_mul, hν u, one_mul]
  calc ∑ a, ∑ b, q u * ν u a * ν u b * ((v a - μ) * (v b - μ))
      = q u * ((∑ a, ν u a * (v a - μ)) * (∑ b, ν u b * (v b - μ))) := by
        rw [Finset.sum_mul_sum, Finset.mul_sum]
        refine Finset.sum_congr rfl fun a _ => ?_
        rw [Finset.mul_sum]
        refine Finset.sum_congr rfl fun b _ => ?_
        ring
    _ = q u * ((∑ a, ν u a * v a) - μ) ^ 2 := by
        rw [key]
        ring

/-- P9 (b), correlation: with `Var(D₁) = σ² ≠ 0`, the covariance of P9 (b)
is `ρ σ²` for `ρ = Var(E[D₁ | U]) / Var(D₁)`. -/
theorem p9b_implied_correlation (c σ2 : ℝ) (hσ : σ2 ≠ 0) : c = (c / σ2) * σ2 := by
  field_simp

/-- P9, numbers: `m = 60` and `ρ = 0.05` give a design effect of 3.95. -/
theorem p9_numbers : (1 : ℝ) + ((60 : ℝ) - 1) * 0.05 = 3.95 := by
  norm_num

/-! ## P10. A shared rate component (the parts that need no integral) -/

/-- The mean of a Poisson(λ) count is `λ`. -/
theorem poissonPMF_mean (lam : ℝ) : HasSum (fun n : ℕ => poissonPMF lam n * (n : ℝ)) lam := by
  have h := (poissonPMF_hasSum_one lam).mul_left lam
  rw [mul_one] at h
  refine hasSum_of_shift _ 1 _ ?_ ?_
  · intro n hn
    have hn0 : n = 0 := by omega
    rw [hn0, Nat.cast_zero, mul_zero]
  · have hfun : (fun m : ℕ => poissonPMF lam (m + 1) * ((m + 1 : ℕ) : ℝ))
        = fun m : ℕ => lam * poissonPMF lam m := by
      funext m
      unfold poissonPMF
      have hm : (m.factorial : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero m)
      have hm1 : ((m + 1 : ℕ) : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (Nat.succ_ne_zero m)
      rw [Nat.factorial_succ, Nat.cast_mul, pow_succ]
      field_simp
    rw [hfun]
    exact h

/-- The mean deviation of a Poisson(λ) count from any centre `c` is `λ − c`. -/
theorem poissonPMF_centered (lam c : ℝ) :
    HasSum (fun n : ℕ => poissonPMF lam n * ((n : ℝ) - c)) (lam - c) := by
  have h := (poissonPMF_mean lam).sub ((poissonPMF_hasSum_one lam).mul_right c)
  rw [one_mul] at h
  have hfun : (fun n : ℕ => poissonPMF lam n * ((n : ℝ) - c))
      = fun n : ℕ => poissonPMF lam n * (n : ℝ) - poissonPMF lam n * c := by
    funext n
    ring
  rw [hfun]
  exact h

/-- P10, mean of a mixed Poisson count: if `N` given the rate is Poisson with
that rate, and the rate `Λ` takes finitely many values, then `E[N] = E[Λ]`. -/
theorem p10_mixed_poisson_mean {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (Λ : Ω → ℝ) :
    ∑ ω, π ω * ∑' n : ℕ, poissonPMF (Λ ω) n * (n : ℝ) = fmean π Λ := by
  unfold fmean
  refine Finset.sum_congr rfl fun ω _ => ?_
  rw [(poissonPMF_mean (Λ ω)).tsum_eq]

/-- P10, covariance of two mixed Poisson counts: if `N₁` and `N₂` are
independent Poisson counts given their rates `Λ₁` and `Λ₂`, and the rates take
finitely many values, then `Cov(N₁, N₂) = Cov(Λ₁, Λ₂)`. The centres are the
means of `N₁` and `N₂` by `p10_mixed_poisson_mean`. -/
theorem p10_mixed_poisson_covariance {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (Λ₁ Λ₂ : Ω → ℝ) :
    ∑ ω, π ω * ∑' n : ℕ, ∑' m : ℕ, poissonPMF (Λ₁ ω) n * poissonPMF (Λ₂ ω) m
        * (((n : ℝ) - fmean π Λ₁) * ((m : ℝ) - fmean π Λ₂))
      = fcov π Λ₁ Λ₂ := by
  unfold fcov
  generalize fmean π Λ₁ = c₁
  generalize fmean π Λ₂ = c₂
  unfold fmean
  refine Finset.sum_congr rfl fun ω _ => ?_
  have hterm : ∀ n m : ℕ, poissonPMF (Λ₁ ω) n * poissonPMF (Λ₂ ω) m
      * (((n : ℝ) - c₁) * ((m : ℝ) - c₂))
      = (poissonPMF (Λ₁ ω) n * ((n : ℝ) - c₁)) * (poissonPMF (Λ₂ ω) m * ((m : ℝ) - c₂)) :=
    fun n m => by ring
  simp_rw [hterm, tsum_mul_left, tsum_mul_right]
  rw [(poissonPMF_centered (Λ₁ ω) c₁).tsum_eq, (poissonPMF_centered (Λ₂ ω) c₂).tsum_eq]

/-- P10, shared component: if `Λ₁ = U + V₁` and `Λ₂ = U + V₂`, and the pairs
`(U, V₂)`, `(V₁, U)`, and `(V₁, V₂)` are uncorrelated, then
`Cov(Λ₁, Λ₂) = Var(U)`. Finite sample space. -/
theorem p10_shared_component_covariance {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (U V₁ V₂ : Ω → ℝ)
    (h1 : fcov π U V₂ = 0) (h2 : fcov π V₁ U = 0) (h3 : fcov π V₁ V₂ = 0) :
    fcov π (fun ω => U ω + V₁ ω) (fun ω => U ω + V₂ ω) = fvar π U := by
  unfold fcov fvar fmean at *
  have ha : ∑ ω, π ω * (U ω + V₁ ω) = ∑ ω, π ω * U ω + ∑ ω, π ω * V₁ ω := by
    rw [← Finset.sum_add_distrib]
    exact Finset.sum_congr rfl fun ω _ => by ring
  have hb : ∑ ω, π ω * (U ω + V₂ ω) = ∑ ω, π ω * U ω + ∑ ω, π ω * V₂ ω := by
    rw [← Finset.sum_add_distrib]
    exact Finset.sum_congr rfl fun ω _ => by ring
  rw [ha, hb]
  generalize ∑ ω, π ω * U ω = a at *
  generalize ∑ ω, π ω * V₁ ω = b at *
  generalize ∑ ω, π ω * V₂ ω = c at *
  have hpt : ∀ ω, π ω * ((U ω + V₁ ω - (a + b)) * (U ω + V₂ ω - (a + c)))
      = π ω * (U ω - a) ^ 2 + π ω * ((U ω - a) * (V₂ ω - c))
        + π ω * ((V₁ ω - b) * (U ω - a)) + π ω * ((V₁ ω - b) * (V₂ ω - c)) :=
    fun ω => by ring
  rw [Finset.sum_congr rfl fun ω _ => hpt ω, Finset.sum_add_distrib, Finset.sum_add_distrib,
    Finset.sum_add_distrib, h1, h2, h3]
  ring

/-- P10, numbers: with `k = 5` and `θ = 8` the mean is `kθ = 40`, the variance
of a benign count is `40 + 40²/5 = 360`, and a shared component of variance
`aθ² = 64a` gives the correlation `64a/360`. -/
theorem p10_numbers (a : ℝ) :
    (5 : ℝ) * 8 = 40 ∧ (40 : ℝ) + 40 ^ 2 / 5 = 360 ∧
      a * (8 : ℝ) ^ 2 / (40 + 40 ^ 2 / 5) = 64 * a / 360 := by
  refine ⟨by norm_num, by norm_num, ?_⟩
  norm_num
  ring

/-! ## P11. Logic of the interval decision rules -/

/-- P11, item 1: with `L ≤ U` it is not the case that both `U ≤ Δ` and
`L > Δ`. -/
theorem p11_not_both (L U Δ : ℝ) (hLU : L ≤ U) : ¬ (U ≤ Δ ∧ Δ < L) := by
  rintro ⟨h1, h2⟩
  linarith

/-- P11, item 2: if `δ > Δ` and `U ≤ Δ`, then `δ` is not in `[L, U]`. -/
theorem p11_support_excludes (L U Δ δ : ℝ) (hδ : Δ < δ) (hU : U ≤ Δ) : ¬ (L ≤ δ ∧ δ ≤ U) := by
  rintro ⟨_, h2⟩
  linarith

/-- P11, item 3: if `δ ≤ Δ` and `L > Δ`, then `δ` is not in `[L, U]`. -/
theorem p11_against_excludes (L U Δ δ : ℝ) (hδ : δ ≤ Δ) (hL : Δ < L) : ¬ (L ≤ δ ∧ δ ≤ U) := by
  rintro ⟨h1, _⟩
  linarith

/-- P11, item 4: if `δ ≤ 0` and `L > 0`, then `δ` is not in `[L, U]`. -/
theorem p11_above_zero_excludes (L U δ : ℝ) (hδ : δ ≤ 0) (hL : 0 < L) : ¬ (L ≤ δ ∧ δ ≤ U) := by
  rintro ⟨h1, _⟩
  linarith

/-- P11: the verdicts support (`U ≤ Δ`), against (`L > Δ`), and inconclusive
(neither) are exhaustive and mutually exclusive when `L ≤ U`. -/
theorem p11_verdicts (L U Δ : ℝ) (hLU : L ≤ U) :
    (U ≤ Δ ∨ Δ < L ∨ (¬ U ≤ Δ ∧ ¬ Δ < L)) ∧ ¬ (U ≤ Δ ∧ Δ < L) ∧
      ¬ (U ≤ Δ ∧ (¬ U ≤ Δ ∧ ¬ Δ < L)) ∧ ¬ (Δ < L ∧ (¬ U ≤ Δ ∧ ¬ Δ < L)) := by
  refine ⟨?_, p11_not_both L U Δ hLU, ?_, ?_⟩
  · by_cases h1 : U ≤ Δ
    · exact Or.inl h1
    · by_cases h2 : Δ < L
      · exact Or.inr (Or.inl h2)
      · exact Or.inr (Or.inr ⟨h1, h2⟩)
  · rintro ⟨h1, h2, _⟩
    exact h2 h1
  · rintro ⟨h1, _, h3⟩
    exact h3 h1

/-- A verdict that excludes the covering event has probability at most `α`
when the covering event has probability at least `1 − α`. Finite sample
space. -/
theorem p11_error_bound_finite {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (hπ0 : ∀ ω, 0 ≤ π ω)
    (hπ : ∑ ω, π ω = 1) (cover verdict : Ω → Prop) [DecidablePred cover] [DecidablePred verdict]
    (α : ℝ) (hcov : 1 - α ≤ ∑ ω, π ω * (if cover ω then 1 else 0))
    (hexcl : ∀ ω, verdict ω → ¬ cover ω) :
    ∑ ω, π ω * (if verdict ω then 1 else 0) ≤ α := by
  have hsum : ∑ ω, π ω * (if verdict ω then 1 else 0) + ∑ ω, π ω * (if cover ω then 1 else 0)
      ≤ ∑ ω, π ω := by
    rw [← Finset.sum_add_distrib]
    refine Finset.sum_le_sum fun ω _ => ?_
    by_cases hv : verdict ω
    · have hc : ¬ cover ω := hexcl ω hv
      rw [ite_eq_left hv, ite_eq_right hc]
      linarith [hπ0 ω]
    · rw [ite_eq_right hv]
      by_cases hc : cover ω
      · rw [ite_eq_left hc]
        linarith [hπ0 ω]
      · rw [ite_eq_right hc]
        linarith [hπ0 ω]
  rw [hπ] at hsum
  linarith

/-- P11, corollary on a finite sample space: if `P(L ≤ δ ≤ U) ≥ 1 − α`, then
support (`U ≤ Δ`) has probability at most `α` when `δ > Δ`, against (`L > Δ`)
has probability at most `α` when `δ ≤ Δ`, and `L > 0` has probability at most
`α` when `δ ≤ 0`. -/
theorem p11_corollary_finite {Ω : Type*} [Fintype Ω] (π : Ω → ℝ) (hπ0 : ∀ ω, 0 ≤ π ω)
    (hπ : ∑ ω, π ω = 1) (L U : Ω → ℝ) (Δ δ α : ℝ)
    (hcov : 1 - α ≤ ∑ ω, π ω * (if L ω ≤ δ ∧ δ ≤ U ω then 1 else 0)) :
    (Δ < δ → ∑ ω, π ω * (if U ω ≤ Δ then 1 else 0) ≤ α) ∧
    (δ ≤ Δ → ∑ ω, π ω * (if Δ < L ω then 1 else 0) ≤ α) ∧
    (δ ≤ 0 → ∑ ω, π ω * (if 0 < L ω then 1 else 0) ≤ α) := by
  refine ⟨fun hδ => ?_, fun hδ => ?_, fun hδ => ?_⟩
  · exact p11_error_bound_finite π hπ0 hπ (fun ω => L ω ≤ δ ∧ δ ≤ U ω) (fun ω => U ω ≤ Δ) α hcov
      (fun ω hU => p11_support_excludes (L ω) (U ω) Δ δ hδ hU)
  · exact p11_error_bound_finite π hπ0 hπ (fun ω => L ω ≤ δ ∧ δ ≤ U ω) (fun ω => Δ < L ω) α hcov
      (fun ω hL => p11_against_excludes (L ω) (U ω) Δ δ hδ hL)
  · exact p11_error_bound_finite π hπ0 hπ (fun ω => L ω ≤ δ ∧ δ ≤ U ω) (fun ω => 0 < L ω) α hcov
      (fun ω hL => p11_above_zero_excludes (L ω) (U ω) δ hδ hL)

/-- The same bound for any probability measure: an event that excludes a
measurable covering event of probability at least `1 − α` has probability at
most `α`. -/
theorem p11_error_bound_measure {Ω : Type*} [MeasurableSpace Ω] (μ : MeasureTheory.Measure Ω)
    (hμ : μ Set.univ = 1) (C E : Set Ω) (hC : MeasurableSet C) (α : ℝ)
    (hcov : ENNReal.ofReal (1 - α) ≤ μ C) (hexcl : E ⊆ Cᶜ) : μ E ≤ ENNReal.ofReal α := by
  have h1 : μ E ≤ μ Cᶜ := MeasureTheory.measure_mono hexcl
  have h2 : μ C + μ Cᶜ = 1 := by rw [MeasureTheory.measure_add_measure_compl hC, hμ]
  by_contra hlt
  rw [not_le] at hlt
  have h3 : ENNReal.ofReal α < μ Cᶜ := lt_of_lt_of_le hlt h1
  have h4 : ENNReal.ofReal (1 - α) + ENNReal.ofReal α < μ C + μ Cᶜ :=
    ENNReal.add_lt_add_of_le_of_lt ENNReal.ofReal_ne_top hcov h3
  have h5 : (1 : ENNReal) ≤ ENNReal.ofReal (1 - α) + ENNReal.ofReal α := by
    have h := ENNReal.ofReal_add_le (p := 1 - α) (q := α)
    rw [sub_add_cancel, ENNReal.ofReal_one] at h
    exact h
  rw [h2] at h4
  exact absurd h5 (not_le.mpr h4)

/-- P11, corollary for any probability measure: if the interval `[L, U]`
covers the true `δ` with probability at least `1 − α`, the three wrong
verdicts each have probability at most `α`. -/
theorem p11_corollary_measure {Ω : Type*} [MeasurableSpace Ω] (μ : MeasureTheory.Measure Ω)
    (hμ : μ Set.univ = 1) (L U : Ω → ℝ) (Δ δ α : ℝ)
    (hC : MeasurableSet {ω | L ω ≤ δ ∧ δ ≤ U ω})
    (hcov : ENNReal.ofReal (1 - α) ≤ μ {ω | L ω ≤ δ ∧ δ ≤ U ω}) :
    (Δ < δ → μ {ω | U ω ≤ Δ} ≤ ENNReal.ofReal α) ∧
    (δ ≤ Δ → μ {ω | Δ < L ω} ≤ ENNReal.ofReal α) ∧
    (δ ≤ 0 → μ {ω | 0 < L ω} ≤ ENNReal.ofReal α) := by
  refine ⟨fun hδ => ?_, fun hδ => ?_, fun hδ => ?_⟩
  · exact p11_error_bound_measure μ hμ _ _ hC α hcov
      (fun ω hU => p11_support_excludes (L ω) (U ω) Δ δ hδ hU)
  · exact p11_error_bound_measure μ hμ _ _ hC α hcov
      (fun ω hL => p11_against_excludes (L ω) (U ω) Δ δ hδ hL)
  · exact p11_error_bound_measure μ hμ _ _ hC α hcov
      (fun ω hL => p11_above_zero_excludes (L ω) (U ω) δ hδ hL)

/-! ## P12. Standardization removes a common scale factor -/

/-- P12: `(c x − c m)/(c s) = (x − m)/s` for `c ≠ 0`. -/
theorem p12_standardize_scale (x m s c : ℝ) (hc : c ≠ 0) :
    (c * x - c * m) / (c * s) = (x - m) / s := by
  rw [← mul_sub, mul_div_mul_left _ _ hc]

/-- P12: the sample multiplied by `c` has mean `c m`. -/
theorem p12_scaled_mean {n : ℕ} (x : Fin n → ℝ) (c : ℝ) :
    (∑ i, c * x i) / (n : ℝ) = c * ((∑ i, x i) / (n : ℝ)) := by
  rw [← Finset.mul_sum, mul_div_assoc]

/-- P12: the sample multiplied by `c ≥ 0` has standard deviation `c s`, for
the divisor `d = n` or `d = n − 1` alike. -/
theorem p12_scaled_sd {n : ℕ} (x : Fin n → ℝ) (c m d : ℝ) (hc : 0 ≤ c) :
    Real.sqrt ((∑ i, (c * x i - c * m) ^ 2) / d)
      = c * Real.sqrt ((∑ i, (x i - m) ^ 2) / d) := by
  have h : (∑ i, (c * x i - c * m) ^ 2) / d = c ^ 2 * ((∑ i, (x i - m) ^ 2) / d) := by
    rw [← mul_div_assoc, Finset.mul_sum]
    congr 1
    refine Finset.sum_congr rfl fun i _ => ?_
    ring
  rw [h, Real.sqrt_mul (sq_nonneg c), Real.sqrt_sq hc]

/-- P12, as cited: a value standardized with the mean and standard deviation
of its own sample is unchanged when the value and the sample are multiplied
by the same `c > 0`. -/
theorem p12_local_standardization {n : ℕ} (x : Fin n → ℝ) (z c d : ℝ) (hc : 0 < c) :
    (c * z - (∑ i, c * x i) / (n : ℝ))
        / Real.sqrt ((∑ i, (c * x i - (∑ j, c * x j) / (n : ℝ)) ^ 2) / d)
      = (z - (∑ i, x i) / (n : ℝ))
        / Real.sqrt ((∑ i, (x i - (∑ j, x j) / (n : ℝ)) ^ 2) / d) := by
  rw [p12_scaled_mean, p12_scaled_sd x c _ d hc.le, p12_standardize_scale _ _ _ c hc.ne']

/-! ## Numeric results certified by exact rational arithmetic -/

/-- The tail of a negative binomial law: the masses from `t` on add up to one
minus the first `t` masses. -/
theorem nbPMF_tail (k : ℕ) (hk : 1 ≤ k) (μ : ℝ) (hμ : 0 < μ) (t : ℕ) :
    HasSum (fun m : ℕ => nbPMF k μ (m + t)) (1 - ∑ n ∈ Finset.range t, nbPMF k μ n) :=
  (hasSum_nat_add_iff' t).mpr (nbPMF_hasSum_one k hk μ hμ)

/-- The first `t` masses of NB(5, 40) as a rational number (`q = 1/9`). -/
theorem nb_p0_partial_sum (t : ℕ) :
    ∑ n ∈ Finset.range t, nbPMF 5 40 n
      = ((∑ n ∈ Finset.range t, ((n + 4).choose 4 : ℚ) * (1 / 9) ^ 5 * (8 / 9) ^ n : ℚ) : ℝ) := by
  push_cast
  refine Finset.sum_congr rfl fun n _ => ?_
  have e : n + 5 - 1 = n + 4 := by omega
  unfold nbPMF
  rw [e]
  norm_num

/-- The first `t` masses of NB(5, 10) as a rational number (`q = 1/3`). -/
theorem nb_pS_partial_sum (t : ℕ) :
    ∑ n ∈ Finset.range t, nbPMF 5 10 n
      = ((∑ n ∈ Finset.range t, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n : ℚ) : ℝ) := by
  push_cast
  refine Finset.sum_congr rfl fun n _ => ?_
  have e : n + 5 - 1 = n + 4 := by omega
  unfold nbPMF
  rw [e]
  norm_num

/-- Numeric result, p0 threshold: for the benign count `B` ~ NB(5, 40),
`P(B ≤ 95) = 0.989539 < 0.99 ≤ P(B ≤ 96) = 0.990355`, so the threshold is 96,
and the achieved false-positive rate `P(B > 96)` is 0.009645. Each six-digit
value is certified to within `5 · 10⁻⁷`. -/
theorem n_threshold_p0 :
    ((0.9895385 : ℝ) ≤ ∑ n ∈ Finset.range 96, nbPMF 5 40 n ∧
      ∑ n ∈ Finset.range 96, nbPMF 5 40 n ≤ 0.9895395) ∧
    ((0.9903545 : ℝ) ≤ ∑ n ∈ Finset.range 97, nbPMF 5 40 n ∧
      ∑ n ∈ Finset.range 97, nbPMF 5 40 n ≤ 0.9903555) ∧
    (∑ n ∈ Finset.range 96, nbPMF 5 40 n < 0.99 ∧
      (0.99 : ℝ) ≤ ∑ n ∈ Finset.range 97, nbPMF 5 40 n) ∧
    ((0.0096445 : ℝ) ≤ 1 - ∑ n ∈ Finset.range 97, nbPMF 5 40 n ∧
      1 - ∑ n ∈ Finset.range 97, nbPMF 5 40 n ≤ 0.0096455) := by
  have h1 : (9895385 / 10000000 : ℚ)
      ≤ ∑ n ∈ Finset.range 96, ((n + 4).choose 4 : ℚ) * (1 / 9) ^ 5 * (8 / 9) ^ n := by
    decide +kernel
  have h2 : (∑ n ∈ Finset.range 96, ((n + 4).choose 4 : ℚ) * (1 / 9) ^ 5 * (8 / 9) ^ n)
      ≤ 9895395 / 10000000 := by
    decide +kernel
  have h3 : (9903545 / 10000000 : ℚ)
      ≤ ∑ n ∈ Finset.range 97, ((n + 4).choose 4 : ℚ) * (1 / 9) ^ 5 * (8 / 9) ^ n := by
    decide +kernel
  have h4 : (∑ n ∈ Finset.range 97, ((n + 4).choose 4 : ℚ) * (1 / 9) ^ 5 * (8 / 9) ^ n)
      ≤ 9903555 / 10000000 := by
    decide +kernel
  have r1 := (Rat.cast_le (K := ℝ)).mpr h1
  have r2 := (Rat.cast_le (K := ℝ)).mpr h2
  have r3 := (Rat.cast_le (K := ℝ)).mpr h3
  have r4 := (Rat.cast_le (K := ℝ)).mpr h4
  rw [← nb_p0_partial_sum] at r1 r2 r3 r4
  have e1 : ((9895385 / 10000000 : ℚ) : ℝ) = 0.9895385 := by norm_num
  have e2 : ((9895395 / 10000000 : ℚ) : ℝ) = 0.9895395 := by norm_num
  have e3 : ((9903545 / 10000000 : ℚ) : ℝ) = 0.9903545 := by norm_num
  have e4 : ((9903555 / 10000000 : ℚ) : ℝ) = 0.9903555 := by norm_num
  rw [e1] at r1
  rw [e2] at r2
  rw [e3] at r3
  rw [e4] at r4
  refine ⟨⟨r1, r2⟩, ⟨r3, r4⟩, ⟨?_, ?_⟩, ⟨?_, ?_⟩⟩
  · linarith
  · linarith
  · linarith
  · linarith

/-- Numeric result, pS threshold: for the benign sampled count `S` ~
NB(5, 10), `P(S ≤ 25) = 0.987770 < 0.99 ≤ P(S ≤ 26) = 0.990748`, so the
threshold is 26 sampled packets, 104 rescaled, and the achieved false-positive
rate `P(S > 26)` is 0.009252. -/
theorem n_threshold_pS :
    ((0.9877695 : ℝ) ≤ ∑ n ∈ Finset.range 26, nbPMF 5 10 n ∧
      ∑ n ∈ Finset.range 26, nbPMF 5 10 n ≤ 0.9877705) ∧
    ((0.9907475 : ℝ) ≤ ∑ n ∈ Finset.range 27, nbPMF 5 10 n ∧
      ∑ n ∈ Finset.range 27, nbPMF 5 10 n ≤ 0.9907485) ∧
    (∑ n ∈ Finset.range 26, nbPMF 5 10 n < 0.99 ∧
      (0.99 : ℝ) ≤ ∑ n ∈ Finset.range 27, nbPMF 5 10 n) ∧
    ((0.0092515 : ℝ) ≤ 1 - ∑ n ∈ Finset.range 27, nbPMF 5 10 n ∧
      1 - ∑ n ∈ Finset.range 27, nbPMF 5 10 n ≤ 0.0092525) ∧
    4 * 26 = 104 := by
  have h1 : (9877695 / 10000000 : ℚ)
      ≤ ∑ n ∈ Finset.range 26, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n := by
    decide +kernel
  have h2 : (∑ n ∈ Finset.range 26, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n)
      ≤ 9877705 / 10000000 := by
    decide +kernel
  have h3 : (9907475 / 10000000 : ℚ)
      ≤ ∑ n ∈ Finset.range 27, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n := by
    decide +kernel
  have h4 : (∑ n ∈ Finset.range 27, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n)
      ≤ 9907485 / 10000000 := by
    decide +kernel
  have r1 := (Rat.cast_le (K := ℝ)).mpr h1
  have r2 := (Rat.cast_le (K := ℝ)).mpr h2
  have r3 := (Rat.cast_le (K := ℝ)).mpr h3
  have r4 := (Rat.cast_le (K := ℝ)).mpr h4
  rw [← nb_pS_partial_sum] at r1 r2 r3 r4
  have e1 : ((9877695 / 10000000 : ℚ) : ℝ) = 0.9877695 := by norm_num
  have e2 : ((9877705 / 10000000 : ℚ) : ℝ) = 0.9877705 := by norm_num
  have e3 : ((9907475 / 10000000 : ℚ) : ℝ) = 0.9907475 := by norm_num
  have e4 : ((9907485 / 10000000 : ℚ) : ℝ) = 0.9907485 := by norm_num
  rw [e1] at r1
  rw [e2] at r2
  rw [e3] at r3
  rw [e4] at r4
  refine ⟨⟨r1, r2⟩, ⟨r3, r4⟩, ⟨?_, ?_⟩, ⟨?_, ?_⟩, by norm_num⟩
  · linarith
  · linarith
  · linarith
  · linarith

/-- Numeric result, the frozen p0 threshold on rescaled pS benign counts:
`4S > 96` is the event `S > 24`, and `P(S > 24) = 0.016100` for `S` ~
NB(5, 10). -/
theorem n_frozen_threshold_fpr :
    (∀ s : ℕ, 96 < 4 * s ↔ 24 < s) ∧
    ((0.0160995 : ℝ) ≤ 1 - ∑ n ∈ Finset.range 25, nbPMF 5 10 n ∧
      1 - ∑ n ∈ Finset.range 25, nbPMF 5 10 n ≤ 0.0161005) := by
  have h1 : (9838995 / 10000000 : ℚ)
      ≤ ∑ n ∈ Finset.range 25, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n := by
    decide +kernel
  have h2 : (∑ n ∈ Finset.range 25, ((n + 4).choose 4 : ℚ) * (1 / 3) ^ 5 * (2 / 3) ^ n)
      ≤ 9839005 / 10000000 := by
    decide +kernel
  have r1 := (Rat.cast_le (K := ℝ)).mpr h1
  have r2 := (Rat.cast_le (K := ℝ)).mpr h2
  rw [← nb_pS_partial_sum] at r1 r2
  have e1 : ((9838995 / 10000000 : ℚ) : ℝ) = 0.9838995 := by norm_num
  have e2 : ((9839005 / 10000000 : ℚ) : ℝ) = 0.9839005 := by norm_num
  rw [e1] at r1
  rw [e2] at r2
  refine ⟨fun s => by omega, ?_, ?_⟩
  · linarith
  · linarith

/-! ## Mean and variance of the negative binomial law (the notation of the design) -/

/-- The series behind the negative binomial mean, with success probability `q`
and `r = 1 − q`. -/
theorem nb_series_mean_core (K : ℕ) (q r : ℝ) (hq : 0 < q) (hr0 : 0 ≤ r) (hqr : 1 - r = q) :
    HasSum (fun n : ℕ => (((n + K).choose K : ℝ) * q ^ (K + 1) * r ^ n) * (n : ℝ))
      (((K : ℝ) + 1) * r / q) := by
  have hr1 : r < 1 := by linarith
  have hser := (choose_geometric_hasSum (K + 1) r hr0 hr1).mul_left
    (((K : ℝ) + 1) * q ^ (K + 1) * r)
  rw [hqr] at hser
  have hval : ((K : ℝ) + 1) * q ^ (K + 1) * r * (1 / q ^ (K + 1 + 1)) = ((K : ℝ) + 1) * r / q := by
    have e : q ^ (K + 1 + 1) = q ^ (K + 1) * q := by ring
    rw [e]
    field_simp
  rw [hval] at hser
  refine hasSum_of_shift _ 1 _ ?_ ?_
  · intro n hn
    have hn0 : n = 0 := by omega
    rw [hn0, Nat.cast_zero, mul_zero]
  · have hfun : (fun m : ℕ =>
          (((m + 1 + K).choose K : ℝ) * q ^ (K + 1) * r ^ (m + 1)) * ((m + 1 : ℕ) : ℝ))
        = fun m : ℕ => ((K : ℝ) + 1) * q ^ (K + 1) * r
            * (((m + (K + 1)).choose (K + 1) : ℝ) * r ^ m) := by
      funext m
      have h := Nat.choose_succ_right_eq (m + 1 + K) K
      have e : m + 1 + K - K = m + 1 := by omega
      rw [e] at h
      have hR : ((m + (K + 1)).choose (K + 1) : ℝ) * ((K : ℝ) + 1)
          = ((m + 1 + K).choose K : ℝ) * ((m + 1 : ℕ) : ℝ) := by
        have e2 : m + (K + 1) = m + 1 + K := by omega
        rw [e2]
        exact_mod_cast h
      rw [pow_succ]
      linear_combination (-(q ^ (K + 1) * r ^ m * r)) * hR
    rw [hfun]
    exact hser

/-- The series behind the second factorial moment of the negative binomial
law. -/
theorem nb_series_fact2_core (K : ℕ) (q r : ℝ) (hq : 0 < q) (hr0 : 0 ≤ r) (hqr : 1 - r = q) :
    HasSum (fun n : ℕ =>
        (((n + K).choose K : ℝ) * q ^ (K + 1) * r ^ n) * ((n : ℝ) * ((n : ℝ) - 1)))
      (((K : ℝ) + 1) * ((K : ℝ) + 2) * r ^ 2 / q ^ 2) := by
  have hr1 : r < 1 := by linarith
  have hser := (choose_geometric_hasSum (K + 2) r hr0 hr1).mul_left
    (((K : ℝ) + 1) * ((K : ℝ) + 2) * q ^ (K + 1) * r ^ 2)
  rw [hqr] at hser
  have hval : ((K : ℝ) + 1) * ((K : ℝ) + 2) * q ^ (K + 1) * r ^ 2 * (1 / q ^ (K + 2 + 1))
      = ((K : ℝ) + 1) * ((K : ℝ) + 2) * r ^ 2 / q ^ 2 := by
    have e : q ^ (K + 2 + 1) = q ^ (K + 1) * q ^ 2 := by ring
    rw [e]
    field_simp
  rw [hval] at hser
  refine hasSum_of_shift _ 2 _ ?_ ?_
  · intro n hn
    have h01 : n = 0 ∨ n = 1 := by omega
    rcases h01 with rfl | rfl <;> simp
  · have hfun : (fun m : ℕ =>
          (((m + 2 + K).choose K : ℝ) * q ^ (K + 1) * r ^ (m + 2))
            * (((m + 2 : ℕ) : ℝ) * (((m + 2 : ℕ) : ℝ) - 1)))
        = fun m : ℕ => ((K : ℝ) + 1) * ((K : ℝ) + 2) * q ^ (K + 1) * r ^ 2
            * (((m + (K + 2)).choose (K + 2) : ℝ) * r ^ m) := by
      funext m
      have h1 := Nat.choose_succ_right_eq (m + 2 + K) K
      have h2 := Nat.choose_succ_right_eq (m + 2 + K) (K + 1)
      have e1 : m + 2 + K - K = m + 2 := by omega
      have e2 : m + 2 + K - (K + 1) = m + 1 := by omega
      rw [e1] at h1
      rw [e2] at h2
      have h3 : (m + 2 + K).choose (K + 2) * (K + 1) * (K + 2)
          = (m + 2 + K).choose K * (m + 2) * (m + 1) := by
        calc (m + 2 + K).choose (K + 2) * (K + 1) * (K + 2)
            = ((m + 2 + K).choose (K + 1 + 1) * (K + 1 + 1)) * (K + 1) := by ring
          _ = ((m + 2 + K).choose (K + 1) * (m + 1)) * (K + 1) := by rw [h2]
          _ = ((m + 2 + K).choose (K + 1) * (K + 1)) * (m + 1) := by ring
          _ = (m + 2 + K).choose K * (m + 2) * (m + 1) := by rw [h1]
      have hR : ((m + (K + 2)).choose (K + 2) : ℝ) * ((K : ℝ) + 1) * ((K : ℝ) + 2)
          = ((m + 2 + K).choose K : ℝ) * ((m : ℝ) + 2) * ((m : ℝ) + 1) := by
        have e3 : m + (K + 2) = m + 2 + K := by omega
        rw [e3]
        exact_mod_cast h3
      rw [pow_add]
      push_cast
      linear_combination (-(q ^ (K + 1) * r ^ m * r ^ 2)) * hR
    rw [hfun]
    exact hser

/-- The mean of NB(k, μ) is `μ` (integer size `k ≥ 1`). -/
theorem nbPMF_mean (k : ℕ) (hk : 1 ≤ k) (μ : ℝ) (hμ : 0 < μ) :
    HasSum (fun n : ℕ => nbPMF k μ n * (n : ℝ)) μ := by
  obtain ⟨K, rfl⟩ : ∃ K, k = K + 1 := ⟨k - 1, by omega⟩
  have hκ : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) := by positivity
  have hD : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) + μ := by positivity
  have hqr : 1 - μ / (((K + 1 : ℕ) : ℝ) + μ) = ((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ) := by
    field_simp
    ring
  have h := nb_series_mean_core K _ _ (div_pos hκ hD) (div_nonneg hμ.le hD.le) hqr
  have hval : ((K : ℝ) + 1) * (μ / (((K + 1 : ℕ) : ℝ) + μ))
      / (((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ)) = μ := by
    push_cast
    have hK : (K : ℝ) + 1 ≠ 0 := by positivity
    have hD' : (K : ℝ) + 1 + μ ≠ 0 := by positivity
    field_simp
  rw [hval] at h
  unfold nbPMF
  have e1 : ∀ n : ℕ, n + (K + 1) - 1 = n + K := fun n => by omega
  have e2 : K + 1 - 1 = K := by omega
  simp only [e1, e2]
  exact h

/-- The second factorial moment of NB(k, μ) is `((k + 1)/k) μ²`. -/
theorem nbPMF_fact2 (k : ℕ) (hk : 1 ≤ k) (μ : ℝ) (hμ : 0 < μ) :
    HasSum (fun n : ℕ => nbPMF k μ n * ((n : ℝ) * ((n : ℝ) - 1)))
      ((((k : ℝ) + 1) / (k : ℝ)) * μ ^ 2) := by
  obtain ⟨K, rfl⟩ : ∃ K, k = K + 1 := ⟨k - 1, by omega⟩
  have hκ : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) := by positivity
  have hD : (0 : ℝ) < ((K + 1 : ℕ) : ℝ) + μ := by positivity
  have hqr : 1 - μ / (((K + 1 : ℕ) : ℝ) + μ) = ((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ) := by
    field_simp
    ring
  have h := nb_series_fact2_core K _ _ (div_pos hκ hD) (div_nonneg hμ.le hD.le) hqr
  have hval : ((K : ℝ) + 1) * ((K : ℝ) + 2) * (μ / (((K + 1 : ℕ) : ℝ) + μ)) ^ 2
      / (((K + 1 : ℕ) : ℝ) / (((K + 1 : ℕ) : ℝ) + μ)) ^ 2
      = ((((K + 1 : ℕ) : ℝ) + 1) / ((K + 1 : ℕ) : ℝ)) * μ ^ 2 := by
    push_cast
    have hK : (K : ℝ) + 1 ≠ 0 := by positivity
    have hD' : (K : ℝ) + 1 + μ ≠ 0 := by positivity
    field_simp
    ring
  rw [hval] at h
  unfold nbPMF
  have e1 : ∀ n : ℕ, n + (K + 1) - 1 = n + K := fun n => by omega
  have e2 : K + 1 - 1 = K := by omega
  simp only [e1, e2]
  exact h

/-- The variance of NB(k, μ) is `μ + μ²/k`, so the dispersion of the design
is `φ = 1/k` (integer size `k ≥ 1`). -/
theorem nbPMF_variance (k : ℕ) (hk : 1 ≤ k) (μ : ℝ) (hμ : 0 < μ) :
    HasSum (fun n : ℕ => nbPMF k μ n * ((n : ℝ) - μ) ^ 2) (μ + μ ^ 2 / (k : ℝ)) := by
  have h0 := nbPMF_hasSum_one k hk μ hμ
  have h1 := nbPMF_mean k hk μ hμ
  have h2 := nbPMF_fact2 k hk μ hμ
  have h := (h2.add (h1.mul_left (1 - 2 * μ))).add (h0.mul_left (μ ^ 2))
  have hfun : (fun n : ℕ => nbPMF k μ n * ((n : ℝ) - μ) ^ 2)
      = fun n : ℕ => nbPMF k μ n * ((n : ℝ) * ((n : ℝ) - 1))
          + (1 - 2 * μ) * (nbPMF k μ n * (n : ℝ)) + μ ^ 2 * nbPMF k μ n := by
    funext n
    ring
  have hk' : (k : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (by omega)
  have hval : ((k : ℝ) + 1) / (k : ℝ) * μ ^ 2 + (1 - 2 * μ) * μ + μ ^ 2 * 1
      = μ + μ ^ 2 / (k : ℝ) := by
    field_simp
    ring
  rw [hfun, ← hval]
  exact h

/-- P3, the planning case: the benign count NB(5, 40) has mean 40 and
variance 360, and the rescaled count `4S` at `p = 1/4` has variance 480. -/
theorem p3_planning_case :
    HasSum (fun n : ℕ => nbPMF 5 40 n * (n : ℝ)) 40 ∧
    HasSum (fun n : ℕ => nbPMF 5 40 n * ((n : ℝ) - 40) ^ 2) 360 ∧
    HasSum (fun n : ℕ => nbPMF 5 40 n
      * ∑ s ∈ Finset.range (n + 1), binomPMF n (1 / 4) s * (4 * (s : ℝ) - 40) ^ 2) 480 := by
  have hm := nbPMF_mean 5 (by norm_num) 40 (by norm_num)
  have hv := nbPMF_variance 5 (by norm_num) 40 (by norm_num)
  have e : (40 : ℝ) + 40 ^ 2 / ((5 : ℕ) : ℝ) = 360 := by norm_num
  rw [e] at hv
  have h := p3_quarter (nbPMF 5 40) 40 360 hm hv
  have e2 : (360 : ℝ) + 3 * 40 = 480 := by norm_num
  rw [e2] at h
  exact ⟨hm, hv, h⟩

/-- P5, the planning case: an attack count Poisson(40 r) sampled at `p = 1/4`
is Poisson(10 r), where `r` is the intensity ratio. -/
theorem p5_planning_case (r : ℝ) (s : ℕ) :
    HasSum (fun a : ℕ => poissonPMF (40 * r) a * binomPMF a (1 / 4) s) (poissonPMF (10 * r) s) := by
  have h := p5_thinned_poisson (40 * r) (1 / 4) s
  have e : (1 / 4 : ℝ) * (40 * r) = 10 * r := by ring
  rw [e] at h
  exact h

/-- P9 (a), covariance-matrix form: if the covariances `c i j` of `m`
variables are `σ²` on the diagonal and `ρ σ²` off it, then
`(1/m²) Σᵢ Σⱼ c i j = (σ²/m)(1 + (m − 1)ρ)`. By bilinearity of the covariance
the left side is the variance of the mean on any probability space. -/
theorem p9a_design_effect_matrix {m : ℕ} (hm : 0 < m) (c : Fin m → Fin m → ℝ) (σ2 ρ : ℝ)
    (hdiag : ∀ i, c i i = σ2) (hoff : ∀ i j, i ≠ j → c i j = ρ * σ2) :
    (1 / (m : ℝ)) ^ 2 * ∑ i, ∑ j, c i j = (σ2 / m) * (1 + ((m : ℝ) - 1) * ρ) := by
  have hij : ∀ i j, c i j = ρ * σ2 + (if i = j then σ2 - ρ * σ2 else 0) := by
    intro i j
    by_cases h : i = j
    · subst h
      rw [ite_eq_left rfl, hdiag]
      ring
    · rw [ite_eq_right h, hoff i j h, add_zero]
  simp_rw [hij]
  simp only [Finset.sum_add_distrib, Finset.sum_const, Finset.card_univ, Fintype.card_fin,
    nsmul_eq_mul, Finset.sum_ite_eq, Finset.mem_univ, ite_true]
  have hm' : (m : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr hm.ne'
  field_simp
  ring

end ThesisVerification.ControlledDesign

#print axioms ThesisVerification.ControlledDesign.sum_prod_ite
#print axioms ThesisVerification.ControlledDesign.selWeight_test
#print axioms ThesisVerification.ControlledDesign.selWeight_sum_one
#print axioms ThesisVerification.ControlledDesign.selWeight_eq
#print axioms ThesisVerification.ControlledDesign.selWeight_nonneg
#print axioms ThesisVerification.ControlledDesign.selWeight_eq_patternWeight
#print axioms ThesisVerification.ControlledDesign.prob_all_selected
#print axioms ThesisVerification.ControlledDesign.prob_none_selected
#print axioms ThesisVerification.ControlledDesign.prob_selected
#print axioms ThesisVerification.ControlledDesign.prob_pair_selected
#print axioms ThesisVerification.ControlledDesign.selected_sum_eq_indicator
#print axioms ThesisVerification.ControlledDesign.weighted_selected_mean
#print axioms ThesisVerification.ControlledDesign.weighted_selected_sq
#print axioms ThesisVerification.ControlledDesign.count_law
#print axioms ThesisVerification.ControlledDesign.binomPMF_eq_pattern_sum
#print axioms ThesisVerification.ControlledDesign.binomPMF_sum_one
#print axioms ThesisVerification.ControlledDesign.binomPMF_mean
#print axioms ThesisVerification.ControlledDesign.binomPMF_second_moment
#print axioms ThesisVerification.ControlledDesign.binomPMF_rescaled_second_moment
#print axioms ThesisVerification.ControlledDesign.p1_conditional_unbiased
#print axioms ThesisVerification.ControlledDesign.p1_unbiased_finite
#print axioms ThesisVerification.ControlledDesign.p1_unbiased
#print axioms ThesisVerification.ControlledDesign.p1_quarter
#print axioms ThesisVerification.ControlledDesign.p1_weighted_unbiased
#print axioms ThesisVerification.ControlledDesign.p1_packets_times_four
#print axioms ThesisVerification.ControlledDesign.p1_bytes_times_four
#print axioms ThesisVerification.ControlledDesign.p1_syn_times_four
#print axioms ThesisVerification.ControlledDesign.p2_conditional_variance
#print axioms ThesisVerification.ControlledDesign.p2_quarter_variance
#print axioms ThesisVerification.ControlledDesign.p2_cv_quarter
#print axioms ThesisVerification.ControlledDesign.p2_cv_bounds
#print axioms ThesisVerification.ControlledDesign.p2_weighted_variance
#print axioms ThesisVerification.ControlledDesign.p2_weighted_variance_le
#print axioms ThesisVerification.ControlledDesign.p2_weighted_quarter
#print axioms ThesisVerification.ControlledDesign.p2_bytes_cv_le
#print axioms ThesisVerification.ControlledDesign.p3_total_variance_finite
#print axioms ThesisVerification.ControlledDesign.p3_total_variance
#print axioms ThesisVerification.ControlledDesign.p3_quarter
#print axioms ThesisVerification.ControlledDesign.p3_overdispersed_quarter
#print axioms ThesisVerification.ControlledDesign.p3_numbers
#print axioms ThesisVerification.ControlledDesign.hasSum_of_shift
#print axioms ThesisVerification.ControlledDesign.choose_geometric_hasSum
#print axioms ThesisVerification.ControlledDesign.real_exp_hasSum
#print axioms ThesisVerification.ControlledDesign.nbPMF_hasSum_one
#print axioms ThesisVerification.ControlledDesign.thinned_nb_series
#print axioms ThesisVerification.ControlledDesign.p4_thinned_nb
#print axioms ThesisVerification.ControlledDesign.p4_planning_case
#print axioms ThesisVerification.ControlledDesign.p4_planning_q
#print axioms ThesisVerification.ControlledDesign.poissonPMF_hasSum_one
#print axioms ThesisVerification.ControlledDesign.p5_thinned_poisson
#print axioms ThesisVerification.ControlledDesign.sum_finset_sum_type
#print axioms ThesisVerification.ControlledDesign.selWeight_disjSum
#print axioms ThesisVerification.ControlledDesign.p5_selected_total
#print axioms ThesisVerification.ControlledDesign.p5_two_groups_independent
#print axioms ThesisVerification.ControlledDesign.binomPMF_point
#print axioms ThesisVerification.ControlledDesign.p5_two_groups_joint_mass
#print axioms ThesisVerification.ControlledDesign.p5_selected_counts_independent
#print axioms ThesisVerification.ControlledDesign.p6a_host_unseen
#print axioms ThesisVerification.ControlledDesign.p6a_quarter
#print axioms ThesisVerification.ControlledDesign.p6b_expected_distinct
#print axioms ThesisVerification.ControlledDesign.p6b_expected_distinct_le
#print axioms ThesisVerification.ControlledDesign.p6b_expected_distinct_lt
#print axioms ThesisVerification.ControlledDesign.p6c_no_constant_factor
#print axioms ThesisVerification.ControlledDesign.p6c_constant_at_one
#print axioms ThesisVerification.ControlledDesign.p6c_quarter_instances
#print axioms ThesisVerification.ControlledDesign.p6d_source_seen
#print axioms ThesisVerification.ControlledDesign.p6d_expected_distinct
#print axioms ThesisVerification.ControlledDesign.p6d_expected_distinct_before
#print axioms ThesisVerification.ControlledDesign.p6d_disjoint_sources
#print axioms ThesisVerification.ControlledDesign.p7_rank_bounds
#print axioms ThesisVerification.ControlledDesign.p7a_exceed_count_le
#print axioms ThesisVerification.ControlledDesign.p7a_rank_rule
#print axioms ThesisVerification.ControlledDesign.p7b_exceeds_iff
#print axioms ThesisVerification.ControlledDesign.p7b_rank_count_le
#print axioms ThesisVerification.ControlledDesign.p7b_rank_count_eq
#print axioms ThesisVerification.ControlledDesign.p7b_last_belowCount
#print axioms ThesisVerification.ControlledDesign.belowCount_comp_perm
#print axioms ThesisVerification.ControlledDesign.p7b_event_iff
#print axioms ThesisVerification.ControlledDesign.p7b_symmetry
#print axioms ThesisVerification.ControlledDesign.p7b_exchangeable_le
#print axioms ThesisVerification.ControlledDesign.p7b_exchangeable_eq
#print axioms ThesisVerification.ControlledDesign.p7_numbers
#print axioms ThesisVerification.ControlledDesign.fmean_const_mul
#print axioms ThesisVerification.ControlledDesign.fmean_sum
#print axioms ThesisVerification.ControlledDesign.fcov_self
#print axioms ThesisVerification.ControlledDesign.p8_mean
#print axioms ThesisVerification.ControlledDesign.p8_variance
#print axioms ThesisVerification.ControlledDesign.p9a_design_effect
#print axioms ThesisVerification.ControlledDesign.p9b_conditional_iid_covariance
#print axioms ThesisVerification.ControlledDesign.p9b_implied_correlation
#print axioms ThesisVerification.ControlledDesign.p9_numbers
#print axioms ThesisVerification.ControlledDesign.poissonPMF_mean
#print axioms ThesisVerification.ControlledDesign.poissonPMF_centered
#print axioms ThesisVerification.ControlledDesign.p10_mixed_poisson_mean
#print axioms ThesisVerification.ControlledDesign.p10_mixed_poisson_covariance
#print axioms ThesisVerification.ControlledDesign.p10_shared_component_covariance
#print axioms ThesisVerification.ControlledDesign.p10_numbers
#print axioms ThesisVerification.ControlledDesign.p11_not_both
#print axioms ThesisVerification.ControlledDesign.p11_support_excludes
#print axioms ThesisVerification.ControlledDesign.p11_against_excludes
#print axioms ThesisVerification.ControlledDesign.p11_above_zero_excludes
#print axioms ThesisVerification.ControlledDesign.p11_verdicts
#print axioms ThesisVerification.ControlledDesign.p11_error_bound_finite
#print axioms ThesisVerification.ControlledDesign.p11_corollary_finite
#print axioms ThesisVerification.ControlledDesign.p11_error_bound_measure
#print axioms ThesisVerification.ControlledDesign.p11_corollary_measure
#print axioms ThesisVerification.ControlledDesign.p12_standardize_scale
#print axioms ThesisVerification.ControlledDesign.p12_scaled_mean
#print axioms ThesisVerification.ControlledDesign.p12_scaled_sd
#print axioms ThesisVerification.ControlledDesign.p12_local_standardization
#print axioms ThesisVerification.ControlledDesign.nbPMF_tail
#print axioms ThesisVerification.ControlledDesign.nb_p0_partial_sum
#print axioms ThesisVerification.ControlledDesign.nb_pS_partial_sum
#print axioms ThesisVerification.ControlledDesign.n_threshold_p0
#print axioms ThesisVerification.ControlledDesign.n_threshold_pS
#print axioms ThesisVerification.ControlledDesign.n_frozen_threshold_fpr
#print axioms ThesisVerification.ControlledDesign.nb_series_mean_core
#print axioms ThesisVerification.ControlledDesign.nb_series_fact2_core
#print axioms ThesisVerification.ControlledDesign.nbPMF_mean
#print axioms ThesisVerification.ControlledDesign.nbPMF_fact2
#print axioms ThesisVerification.ControlledDesign.nbPMF_variance
#print axioms ThesisVerification.ControlledDesign.p3_planning_case
#print axioms ThesisVerification.ControlledDesign.p5_planning_case
#print axioms ThesisVerification.ControlledDesign.p9a_design_effect_matrix
