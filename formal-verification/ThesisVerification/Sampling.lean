module

public import Mathlib.Algebra.BigOperators.Field
public import Mathlib.Data.Nat.Choose.Sum
public import Mathlib.Basic.Real.Basic
public import Mathlib.Tactic.Linarith
public import Mathlib.Tactic.NormNum

public section

set_option warningAsError true

/-!
Source: the RQ2 sampling analysis,
`rq2-sampling-analysis-20261115/ANALYSIS.md` (sections 1 to 5).
`sampling-source-map.json` gives the locator, meaning, assumptions, and scope
of every theorem.

All statements are exact and data-free. The first group describes independent
selection of each packet with probability `p` (a product weight on retention
patterns). The second group bounds the recall of any decision rule that reads
only a key, when attack and benign records share keys. The theorems do not
establish that the implemented HMAC-SHA256 selector behaves as independent
selection, do not model the flow meter, and do not concern any measured count
or any learned model.
-/

namespace ThesisVerification.Sampling

open scoped BigOperators

/-! ## Independent packet selection with probability `p` -/

/-- Weight of one retention pattern of a flow of `n` packets: `T` is the set of
retained packets, each packet is retained with probability `p` and dropped with
probability `1 − p`, independently. -/
noncomputable def patternWeight (p : ℝ) {n : ℕ} (T : Finset (Fin n)) : ℝ :=
  ∏ i : Fin n, if i ∈ T then p else 1 - p

/-- The weight of a pattern depends only on how many packets it retains. -/
theorem patternWeight_eq (p : ℝ) {n : ℕ} (T : Finset (Fin n)) :
    patternWeight p T = p ^ T.card * (1 - p) ^ (n - T.card) := by
  unfold patternWeight
  rw [Finset.prod_ite, Finset.prod_const, Finset.prod_const]
  have h1 : (Finset.univ.filter fun i : Fin n => i ∈ T) = T := by
    ext i
    simp
  have h2 : (Finset.univ.filter fun i : Fin n => i ∉ T) = Tᶜ := by
    ext i
    simp
  rw [h1, h2, Finset.card_compl, Fintype.card_fin]

/-- The pattern weights add up to one, for every real `p`. With `0 ≤ p ≤ 1`
they are therefore a probability distribution on retention patterns. -/
theorem patternWeight_sum_one (p : ℝ) (n : ℕ) :
    ∑ T : Finset (Fin n), patternWeight p T = 1 := by
  have h := Finset.sum_pow_mul_eq_add_pow p (1 - p) (Finset.univ : Finset (Fin n))
  simp only [Finset.powerset_univ, Finset.card_univ, Fintype.card_fin] at h
  simp_rw [patternWeight_eq]
  rw [h]
  norm_num

/-- With `0 ≤ p ≤ 1` every pattern weight is nonnegative. -/
theorem patternWeight_nonneg (p : ℝ) (hp0 : 0 ≤ p) (hp1 : p ≤ 1) {n : ℕ}
    (T : Finset (Fin n)) : 0 ≤ patternWeight p T := by
  rw [patternWeight_eq]
  have : (0 : ℝ) ≤ 1 - p := by linarith
  positivity

/-- Evidence deletion: no packet of an `n`-packet flow is retained with
probability `(1 − p)ⁿ`, so the flow yields no record. -/
theorem deletion_probability (p : ℝ) (n : ℕ) :
    patternWeight p (∅ : Finset (Fin n)) = (1 - p) ^ n := by
  rw [patternWeight_eq]
  simp

/-- Exactly one given packet `j` is retained, and no other, with probability
`p (1 − p)ⁿ⁻¹`. -/
theorem only_one_packet_retained (p : ℝ) {n : ℕ} (j : Fin n) :
    patternWeight p ({j} : Finset (Fin n)) = p * (1 - p) ^ (n - 1) := by
  rw [patternWeight_eq]
  simp

/-- The collision event: of `n + 1` packets, exactly the first one is retained
with probability `p (1 − p)ⁿ`. -/
theorem first_packet_only (p : ℝ) (n : ℕ) :
    patternWeight p ({0} : Finset (Fin (n + 1))) = p * (1 - p) ^ n := by
  rw [only_one_packet_retained]
  simp

/-- The number of retained packets is binomial: exactly `k` of `n` packets are
retained with probability `C(n, k) pᵏ (1 − p)ⁿ⁻ᵏ`. -/
theorem retained_count_binomial (p : ℝ) (n k : ℕ) :
    ∑ T ∈ (Finset.univ : Finset (Fin n)).powersetCard k, patternWeight p T
      = (n.choose k : ℝ) * p ^ k * (1 - p) ^ (n - k) := by
  have h : ∀ T ∈ (Finset.univ : Finset (Fin n)).powersetCard k,
      patternWeight p T = p ^ k * (1 - p) ^ (n - k) := by
    intro T hT
    rw [patternWeight_eq, (Finset.mem_powersetCard.mp hT).2]
  rw [Finset.sum_congr rfl h, Finset.sum_const, Finset.card_powersetCard, Finset.card_univ,
    Fintype.card_fin, nsmul_eq_mul]
  ring

/-- At least one packet is retained, so the flow yields at least one record,
with probability `1 − (1 − p)ⁿ`. -/
theorem some_packet_retained (p : ℝ) (n : ℕ) :
    ∑ T ∈ (Finset.univ : Finset (Finset (Fin n))).erase ∅, patternWeight p T
      = 1 - (1 - p) ^ n := by
  have h := Finset.add_sum_erase (Finset.univ : Finset (Finset (Fin n))) (patternWeight p)
    (Finset.mem_univ (∅ : Finset (Fin n)))
  rw [patternWeight_sum_one, deletion_probability] at h
  linarith

/-- The selection rule `variate · 4 < 1 · 2²⁵⁶` of the implemented selector is
the same as `variate < 2²⁵⁴`: exactly one quarter of the 2²⁵⁶ values of the
variate select the packet. -/
theorem selection_threshold_quarter (v : ℕ) : v * 4 < 1 * 2 ^ 256 ↔ v < 2 ^ 254 := by
  have h : (2 : ℕ) ^ 256 = 4 * 2 ^ 254 := by norm_num
  rw [h]
  generalize (2 : ℕ) ^ 254 = m
  omega

/-- The numerical instances used in the analysis, for `p = 1/4`: a one-packet
flow is deleted with probability 3/4; a two-packet transaction with 9/16; a
six-packet transaction with 729/4096; a six-packet transaction keeps exactly
its first packet with probability 243/4096; the expected number of records of
the six-packet TCP transaction is 3623/4096; and the share of SYN-only records
among benign records, at one TCP per UDP transaction, is 81/1805. -/
theorem quarter_sampling_instances :
    (1 - (1 / 4 : ℝ)) ^ 1 = 3 / 4 ∧
    (1 - (1 / 4 : ℝ)) ^ 2 = 9 / 16 ∧
    (1 - (1 / 4 : ℝ)) ^ 6 = 729 / 4096 ∧
    (1 / 4 : ℝ) * (1 - 1 / 4) ^ 5 = 243 / 4096 ∧
    (1 - (1 - (1 / 4 : ℝ)) ^ 5) + (1 / 4) * (1 / 4 + (1 - 1 / 4) ^ 5) = 3623 / 4096 ∧
    (243 / 4096 : ℝ) / (3623 / 4096 + (1 - (1 - 1 / 4) ^ 2)) = 81 / 1805 := by
  norm_num

/-! ## Identical keys and the recall ceiling -/

/-- Two records with the same key receive the same decision from every rule
that reads only the key. -/
theorem identical_key_same_decision {Record K D : Type*} (key : Record → K) (rule : K → D)
    (x y : Record) (h : key x = key y) : rule (key x) = rule (key y) :=
  congrArg rule h

/-- If the benign false-positive rate is at most `α`, the alert probability on
a key of benign mass `b x > 0` is at most `α / b x`. Here `φ x` is the
probability that the rule alerts on key `x`. -/
theorem alert_rate_on_key_le {K : Type*} [Fintype K] (b φ : K → ℝ) (α : ℝ)
    (hb : ∀ x, 0 ≤ b x) (hφ0 : ∀ x, 0 ≤ φ x)
    (hfpr : ∑ x, b x * φ x ≤ α) (x : K) (hx : 0 < b x) : φ x ≤ α / b x := by
  have h1 : b x * φ x ≤ ∑ y, b y * φ y :=
    Finset.single_le_sum (f := fun y => b y * φ y)
      (fun y _ => mul_nonneg (hb y) (hφ0 y)) (Finset.mem_univ x)
  rw [le_div_iff₀ hx]
  linarith [mul_comm (b x) (φ x)]

/-- Recall ceiling. Let `a` and `b` be the attack and benign masses of the
keys, `φ` the alert probability of a rule that reads only the key, and `C` a
set of keys on which the attack mass is at most `lam` times the benign mass.
If the benign false-positive rate is at most `α`, the recall is at most the
attack mass outside `C` plus `lam · α`. -/
theorem recall_ceiling {K : Type*} [Fintype K] [DecidableEq K] (a b φ : K → ℝ)
    (C : Finset K) (α lam : ℝ)
    (ha : ∀ x, 0 ≤ a x) (hb : ∀ x, 0 ≤ b x) (hφ0 : ∀ x, 0 ≤ φ x) (hφ1 : ∀ x, φ x ≤ 1)
    (hlam : 0 ≤ lam) (hC : ∀ x ∈ C, a x ≤ lam * b x)
    (hfpr : ∑ x, b x * φ x ≤ α) :
    ∑ x, a x * φ x ≤ ∑ x ∈ Cᶜ, a x + lam * α := by
  rw [← Finset.sum_add_sum_compl C (fun x => a x * φ x)]
  have h1 : ∑ x ∈ C, a x * φ x ≤ lam * ∑ x ∈ C, b x * φ x := by
    rw [Finset.mul_sum]
    refine Finset.sum_le_sum fun x hx => ?_
    have := mul_le_mul_of_nonneg_right (hC x hx) (hφ0 x)
    linarith [mul_assoc lam (b x) (φ x)]
  have h2 : ∑ x ∈ C, b x * φ x ≤ ∑ x, b x * φ x :=
    Finset.sum_le_sum_of_subset_of_nonneg (Finset.subset_univ C)
      fun x _ _ => mul_nonneg (hb x) (hφ0 x)
  have h3 : ∑ x ∈ Cᶜ, a x * φ x ≤ ∑ x ∈ Cᶜ, a x :=
    Finset.sum_le_sum fun x _ => mul_le_of_le_one_right (ha x) (hφ1 x)
  have h4 := mul_le_mul_of_nonneg_left (h2.trans hfpr) hlam
  linarith

/-- One colliding key. If the attack masses add up to one and key `x` has
benign mass `b x > 0`, the recall at benign false-positive rate at most `α` is
at most `1 − a x + a x · (α / b x)`. -/
theorem single_key_recall_ceiling {K : Type*} [Fintype K] [DecidableEq K] (a b φ : K → ℝ)
    (x : K) (α : ℝ)
    (ha : ∀ y, 0 ≤ a y) (hb : ∀ y, 0 ≤ b y) (hφ0 : ∀ y, 0 ≤ φ y) (hφ1 : ∀ y, φ y ≤ 1)
    (hx : 0 < b x) (hsum : ∑ y, a y = 1) (hfpr : ∑ y, b y * φ y ≤ α) :
    ∑ y, a y * φ y ≤ 1 - a x + a x * (α / b x) := by
  have hC : ∀ y ∈ ({x} : Finset K), a y ≤ a x / b x * b y := by
    intro y hy
    rw [Finset.mem_singleton.mp hy, div_mul_cancel₀ _ hx.ne']
  have h := recall_ceiling a b φ {x} α (a x / b x) ha hb hφ0 hφ1
    (div_nonneg (ha x) hx.le) hC hfpr
  have hcompl : ∑ y ∈ ({x} : Finset K)ᶜ, a y = 1 - a x := by
    have := Finset.sum_add_sum_compl ({x} : Finset K) a
    rw [Finset.sum_singleton, hsum] at this
    linarith
  rw [hcompl] at h
  have hring : a x / b x * α = a x * (α / b x) := by ring
  linarith

/-- All attack mass on one key. If every attack record has the key `x`
(`a x = 1` and the attack masses add up to one), the recall is at most
`α / b x`. -/
theorem all_mass_one_key_recall_le {K : Type*} [Fintype K] [DecidableEq K] (a b φ : K → ℝ)
    (x : K) (α : ℝ)
    (ha : ∀ y, 0 ≤ a y) (hb : ∀ y, 0 ≤ b y) (hφ0 : ∀ y, 0 ≤ φ y) (hφ1 : ∀ y, φ y ≤ 1)
    (hx : 0 < b x) (hsum : ∑ y, a y = 1) (hax : a x = 1) (hfpr : ∑ y, b y * φ y ≤ α) :
    ∑ y, a y * φ y ≤ α / b x := by
  have h := single_key_recall_ceiling a b φ x α ha hb hφ0 hφ1 hx hsum hfpr
  rw [hax] at h
  linarith

/-- A deterministic rule cannot alert on a key whose benign mass exceeds the
false-positive budget `α`. -/
theorem deterministic_no_alert_on_heavy_key {K : Type*} [Fintype K] (b : K → ℝ)
    (h : K → Bool) (α : ℝ) (hb : ∀ x, 0 ≤ b x)
    (hfpr : ∑ x, (if h x then b x else 0) ≤ α) (x : K) (hx : α < b x) : h x = false := by
  by_contra hne
  have htrue : h x = true := by simpa using hne
  have h1 : (if h x then b x else 0) ≤ ∑ y, (if h y then b y else 0) :=
    Finset.single_le_sum (f := fun y => if h y then b y else 0)
      (fun y _ => by split_ifs <;> simp [hb y]) (Finset.mem_univ x)
  rw [htrue] at h1
  simp only [ite_true] at h1
  linarith

/-- Deterministic recall ceiling. If every key in `C` has benign mass above
`α`, a deterministic rule with benign false-positive rate at most `α` alerts
on no key of `C`, so its recall is at most the attack mass outside `C`. -/
theorem deterministic_recall_ceiling {K : Type*} [Fintype K] [DecidableEq K] (a b : K → ℝ)
    (h : K → Bool) (C : Finset K) (α : ℝ) (ha : ∀ x, 0 ≤ a x) (hb : ∀ x, 0 ≤ b x)
    (hfpr : ∑ x, (if h x then b x else 0) ≤ α) (hC : ∀ x ∈ C, α < b x) :
    ∑ x, (if h x then a x else 0) ≤ ∑ x ∈ Cᶜ, a x := by
  rw [← Finset.sum_add_sum_compl C (fun x => if h x then a x else 0)]
  have h1 : ∑ x ∈ C, (if h x then a x else 0) = 0 := by
    refine Finset.sum_eq_zero fun x hx => ?_
    rw [deterministic_no_alert_on_heavy_key b h α hb hfpr x (hC x hx)]
    simp
  have h2 : ∑ x ∈ Cᶜ, (if h x then a x else 0) ≤ ∑ x ∈ Cᶜ, a x :=
    Finset.sum_le_sum fun x _ => by split_ifs <;> simp [ha x]
  linarith

end ThesisVerification.Sampling

#print axioms ThesisVerification.Sampling.patternWeight_eq
#print axioms ThesisVerification.Sampling.patternWeight_sum_one
#print axioms ThesisVerification.Sampling.patternWeight_nonneg
#print axioms ThesisVerification.Sampling.deletion_probability
#print axioms ThesisVerification.Sampling.only_one_packet_retained
#print axioms ThesisVerification.Sampling.first_packet_only
#print axioms ThesisVerification.Sampling.retained_count_binomial
#print axioms ThesisVerification.Sampling.some_packet_retained
#print axioms ThesisVerification.Sampling.selection_threshold_quarter
#print axioms ThesisVerification.Sampling.quarter_sampling_instances
#print axioms ThesisVerification.Sampling.identical_key_same_decision
#print axioms ThesisVerification.Sampling.alert_rate_on_key_le
#print axioms ThesisVerification.Sampling.recall_ceiling
#print axioms ThesisVerification.Sampling.single_key_recall_ceiling
#print axioms ThesisVerification.Sampling.all_mass_one_key_recall_le
#print axioms ThesisVerification.Sampling.deterministic_no_alert_on_heavy_key
#print axioms ThesisVerification.Sampling.deterministic_recall_ceiling
