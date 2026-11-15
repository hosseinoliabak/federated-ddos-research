module

public import Mathlib.Analysis.SpecialFunctions.Log.Deriv
public import Mathlib.Analysis.Convex.Deriv
public import Mathlib.Analysis.Convex.Combination
public import Mathlib.Analysis.Convex.Mul
public import Mathlib.Data.Fin.Tuple.Sort
public import Mathlib.Data.Nat.Choose.Sum
public import Mathlib.MeasureTheory.Measure.Map
public import ThesisVerification.Aggregation

public section

set_option warningAsError true

/-!
Source: thesis Chapter 2, "Conceptual and Mathematical Foundations"
(02-foundations.tex, version ch2-v8), equations (2.1)--(2.12) and the claims
stated around them. `foundations-source-map.json` gives the exact locator,
transcription, assumptions, and scope of every theorem.

All statements are exact real-number or finite-combinatorial facts. They do
not establish floating-point behaviour, the training implementation,
convergence, the probabilistic guarantee of Tong et al. (Proposition 1), or
any detection result.
-/

namespace ThesisVerification.Foundations

open scoped BigOperators

/-! ## Logistic regression and binary cross-entropy: Eqs. (2.1)--(2.3) -/

/-- The sigmoid of Eq. (2.1). -/
noncomputable def sigmoid (z : ℝ) : ℝ := 1 / (1 + Real.exp (-z))

/-- The per-record BCE loss of Eq. (2.2), as a function of label and logit. -/
noncomputable def bce (y z : ℝ) : ℝ :=
  -y * Real.log (sigmoid z) - (1 - y) * Real.log (1 - sigmoid z)

/-- Text after Eq. (2.1): the sigmoid lies strictly between 0 and 1. -/
theorem sigmoid_between (z : ℝ) : 0 < sigmoid z ∧ sigmoid z < 1 := by
  have he : 0 < Real.exp (-z) := Real.exp_pos _
  unfold sigmoid
  constructor
  · positivity
  · rw [div_lt_one (by positivity)]
    linarith

/-- Section 2.3, last paragraph: the sigmoid is an increasing function. -/
theorem sigmoid_strictMono : StrictMono sigmoid := by
  intro a b hab
  have ha : 0 < Real.exp (-a) := Real.exp_pos _
  have hb : 0 < Real.exp (-b) := Real.exp_pos _
  have hexp : Real.exp (-b) < Real.exp (-a) := Real.exp_lt_exp.mpr (by linarith)
  unfold sigmoid
  exact one_div_lt_one_div_of_lt (by positivity) (by linarith)

/-- Thresholding the logit and thresholding the sigmoid give the same decision. -/
theorem logit_threshold_iff_sigmoid_threshold (z τ : ℝ) :
    τ < z ↔ sigmoid τ < sigmoid z :=
  sigmoid_strictMono.lt_iff_lt.symm

/-- Closed form of Eq. (2.2) that is valid for every real label value. -/
theorem bce_closed_form (y z : ℝ) :
    bce y z = (1 - y) * z + Real.log (1 + Real.exp (-z)) := by
  have he : 0 < Real.exp (-z) := Real.exp_pos _
  have hpos : 0 < 1 + Real.exp (-z) := by positivity
  have h1 : Real.log (sigmoid z) = -Real.log (1 + Real.exp (-z)) := by
    unfold sigmoid
    rw [one_div, Real.log_inv]
  have h2 : Real.log (1 - sigmoid z) = -z - Real.log (1 + Real.exp (-z)) := by
    have hrew : 1 - sigmoid z = Real.exp (-z) / (1 + Real.exp (-z)) := by
      unfold sigmoid
      field_simp
      ring
    rw [hrew, Real.log_div he.ne' hpos.ne', Real.log_exp]
  unfold bce
  rw [h1, h2]
  ring

/-- Text after Eq. (2.2): with labels in {0,1} and ỹ = 2y − 1, the BCE loss
equals the log-loss log(1 + exp(−ỹ z)). -/
theorem bce_eq_logloss (y z : ℝ) (hy : y = 0 ∨ y = 1) :
    bce y z = Real.log (1 + Real.exp (-((2 * y - 1) * z))) := by
  rw [bce_closed_form]
  rcases hy with rfl | rfl
  · have he : 0 < Real.exp (-z) := Real.exp_pos _
    have hpos : 0 < 1 + Real.exp (-z) := by positivity
    have hrew : 1 + Real.exp (-((2 * 0 - 1) * z)) = Real.exp z * (1 + Real.exp (-z)) := by
      rw [mul_add, ← Real.exp_add]
      norm_num
      ring
    rw [hrew, Real.log_mul (Real.exp_pos z).ne' hpos.ne', Real.log_exp]
    ring
  · norm_num

/-- Derivative of the per-record loss with respect to the logit: σ(z) − y. -/
theorem hasDerivAt_bce (y z : ℝ) : HasDerivAt (bce y) (sigmoid z - y) z := by
  have he : 0 < Real.exp (-z) := Real.exp_pos _
  have hpos : 0 < 1 + Real.exp (-z) := by positivity
  have hfun : bce y = fun t => (1 - y) * t + Real.log (1 + Real.exp (-t)) := by
    funext t
    exact bce_closed_form y t
  have hexp : HasDerivAt (fun t : ℝ => 1 + Real.exp (-t)) (-Real.exp (-z)) z := by
    have h := ((hasDerivAt_neg z).exp).const_add 1
    simpa using h
  have hlog := hexp.log hpos.ne'
  have hlin : HasDerivAt (fun t : ℝ => (1 - y) * t) (1 - y) z := by
    simpa using (hasDerivAt_id z).const_mul (1 - y)
  have hsum := hlin.add hlog
  rw [hfun]
  convert hsum using 1
  unfold sigmoid
  field_simp
  ring

/-- Chain rule along one parameter coordinate. If the logit depends on the
coordinate `t` as `a * t + c`, the loss has derivative `(σ(z) − y) * a`.
With `a = x_j` this is the weight derivative, and with `a = 1` the bias
derivative. -/
theorem hasDerivAt_bce_coordinate (y a c t : ℝ) :
    HasDerivAt (fun s => bce y (a * s + c)) ((sigmoid (a * t + c) - y) * a) t := by
  have hinner : HasDerivAt (fun s : ℝ => a * s + c) a t := by
    simpa using ((hasDerivAt_id t).const_mul a).add_const c
  exact (hasDerivAt_bce y (a * t + c)).comp t hinner

/-- Partial derivative of the objective of Eq. (2.3) along one parameter `t`.
Record `i` has logit `a i * t + c i`, the remaining squared parameters sum to
`r`, and `pen` is `λ` for a penalized parameter or `0` for an unpenalized one. -/
theorem hasDerivAt_objective_coordinate {n : ℕ} (a c y : Fin n → ℝ) (pen r t : ℝ) :
    HasDerivAt
      (fun s => (1 / (n : ℝ)) * ∑ i, bce (y i) (a i * s + c i) + pen / 2 * (s ^ 2 + r))
      ((1 / (n : ℝ)) * ∑ i, (sigmoid (a i * t + c i) - y i) * a i + pen * t) t := by
  have hsum : HasDerivAt (fun s => ∑ i, bce (y i) (a i * s + c i))
      (∑ i, (sigmoid (a i * t + c i) - y i) * a i) t :=
    HasDerivAt.fun_sum fun i _ => hasDerivAt_bce_coordinate (y i) (a i) (c i) t
  have hpen : HasDerivAt (fun s : ℝ => pen / 2 * (s ^ 2 + r)) (pen * t) t := by
    have hsq : HasDerivAt (fun s : ℝ => s ^ 2) (2 * t) t := by
      simpa using hasDerivAt_pow 2 t
    have h := (hsq.add_const r).const_mul (pen / 2)
    convert h using 1
    ring
  exact (hsum.const_mul (1 / (n : ℝ))).add hpen

/-- The per-record loss is convex in the logit, for every label value. -/
theorem bce_convex (y : ℝ) : ConvexOn ℝ Set.univ (bce y) := by
  have hdiff : Differentiable ℝ (bce y) := fun z => (hasDerivAt_bce y z).differentiableAt
  have hderiv : deriv (bce y) = fun z => sigmoid z - y := by
    funext z
    exact (hasDerivAt_bce y z).deriv
  apply Monotone.convexOn_univ_of_deriv hdiff
  rw [hderiv]
  intro a b hab
  have := sigmoid_strictMono.monotone hab
  linarith

/-- The logistic-regression objective of Eq. (2.3) with weights `p.1`, bias
`p.2`, records `x i` with labels `y i`, and the L2 penalty on all parameters. -/
noncomputable def lrObjective {n d : ℕ} (x : Fin n → Fin d → ℝ) (y : Fin n → ℝ)
    (lam : ℝ) (p : (Fin d → ℝ) × ℝ) : ℝ :=
  (1 / (n : ℝ)) * ∑ i, bce (y i) (∑ j, p.1 j * x i j + p.2) +
    lam / 2 * (∑ j, p.1 j ^ 2 + p.2 ^ 2)

/-- Text after Eq. (2.3): for logistic regression the objective is convex. -/
theorem lrObjective_convex {n d : ℕ} (x : Fin n → Fin d → ℝ) (y : Fin n → ℝ)
    (lam : ℝ) (hlam : 0 ≤ lam) : ConvexOn ℝ Set.univ (lrObjective x y lam) := by
  refine ⟨convex_univ, ?_⟩
  intro p _ q _ s t hs ht hst
  have hlogit : ∀ i, (∑ j, (s • p + t • q).1 j * x i j + (s • p + t • q).2)
      = s * (∑ j, p.1 j * x i j + p.2) + t * (∑ j, q.1 j * x i j + q.2) := by
    intro i
    simp only [Prod.fst_add, Prod.snd_add, Prod.smul_fst, Prod.smul_snd, Pi.add_apply,
      Pi.smul_apply, smul_eq_mul]
    have hsplit : ∑ j, (s * p.1 j + t * q.1 j) * x i j
        = s * ∑ j, p.1 j * x i j + t * ∑ j, q.1 j * x i j := by
      rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib]
      exact Finset.sum_congr rfl fun j _ => by ring
    rw [hsplit]
    ring
  have hbce : ∀ i, bce (y i) (∑ j, (s • p + t • q).1 j * x i j + (s • p + t • q).2)
      ≤ s * bce (y i) (∑ j, p.1 j * x i j + p.2) + t * bce (y i) (∑ j, q.1 j * x i j + q.2) := by
    intro i
    rw [hlogit i]
    have h := (bce_convex (y i)).2 (Set.mem_univ (∑ j, p.1 j * x i j + p.2))
      (Set.mem_univ (∑ j, q.1 j * x i j + q.2)) hs ht hst
    simpa only [smul_eq_mul] using h
  have hsq : ∀ u v : ℝ, (s * u + t * v) ^ 2 ≤ s * u ^ 2 + t * v ^ 2 := by
    intro u v
    have ht' : t = 1 - s := by linarith
    subst ht'
    nlinarith [mul_nonneg hs ht, sq_nonneg (u - v)]
  have hdata : ∑ i, bce (y i) (∑ j, (s • p + t • q).1 j * x i j + (s • p + t • q).2)
      ≤ s * ∑ i, bce (y i) (∑ j, p.1 j * x i j + p.2)
        + t * ∑ i, bce (y i) (∑ j, q.1 j * x i j + q.2) := by
    rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib]
    exact Finset.sum_le_sum fun i _ => hbce i
  have hpen : (∑ j, (s • p + t • q).1 j ^ 2 + (s • p + t • q).2 ^ 2)
      ≤ s * (∑ j, p.1 j ^ 2 + p.2 ^ 2) + t * (∑ j, q.1 j ^ 2 + q.2 ^ 2) := by
    have h1 : ∑ j, (s • p + t • q).1 j ^ 2 ≤ s * ∑ j, p.1 j ^ 2 + t * ∑ j, q.1 j ^ 2 := by
      rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib]
      refine Finset.sum_le_sum fun j _ => ?_
      simpa using hsq (p.1 j) (q.1 j)
    have h2 : (s • p + t • q).2 ^ 2 ≤ s * p.2 ^ 2 + t * q.2 ^ 2 := by
      simpa using hsq p.2 q.2
    linarith
  have hn : 0 ≤ 1 / (n : ℝ) := by positivity
  have hl : 0 ≤ lam / 2 := by positivity
  have hA := mul_le_mul_of_nonneg_left hdata hn
  have hB := mul_le_mul_of_nonneg_left hpen hl
  simp only [lrObjective, smul_eq_mul]
  linarith

/-- Section 2.3: parameter counts d+1 and 8d+17, the model names LR15, MLP129,
LR3, MLP33, and the 14 inputs of template W in six groups (Section 2.2). -/
theorem parameter_counts :
    (∀ d : ℕ, 8 * d + 8 + 8 + 1 = 8 * d + 17) ∧
    (14 + 1 = 15) ∧ (8 * 14 + 17 = 129) ∧ (2 + 1 = 3) ∧ (8 * 2 + 17 = 33) ∧
    (2 + 1 + 1 + 6 + 2 + 2 = 14) := by
  refine ⟨fun d => by omega, ?_, ?_, ?_, ?_, ?_⟩ <;> norm_num

/-- Section 2.2: a single-packet flow under independent selection with
probability 1/4 is missed with probability (1 − 1/4)^1 = 0.75. Only the
arithmetic is checked; the independence model is the chapter's premise. -/
theorem sampling_miss_single_packet : (1 - (1 / 4 : ℝ)) ^ 1 = 0.75 := by
  norm_num

/-! ## SGD and Adam: Eqs. (2.5)--(2.7) -/

/-- Sign of Eq. (2.5), scalar case: moving against the derivative `g` gives the
map η ↦ F(w − η g) the derivative −g² ≤ 0 at η = 0. -/
theorem sgd_step_descent_scalar (F : ℝ → ℝ) (w g : ℝ) (hF : HasDerivAt F g w) :
    HasDerivAt (fun η => F (w - η * g)) (-(g * g)) 0 ∧ -(g * g) ≤ 0 := by
  constructor
  · have hinner : HasDerivAt (fun η : ℝ => w - η * g) (-g) 0 := by
      simpa using ((hasDerivAt_id (0 : ℝ)).mul_const g).const_sub w
    have hF' : HasDerivAt F g (w - 0 * g) := by simpa using hF
    have h := hF'.comp 0 hinner
    have hval : g * -g = -(g * g) := by ring
    rw [hval] at h
    exact h
  · nlinarith [mul_self_nonneg g]

/-- One coordinate of an Adam moving average, Eq. (2.6), started at zero. -/
noncomputable def adamMoment (β : ℝ) (g : ℕ → ℝ) : ℕ → ℝ
  | 0 => 0
  | t + 1 => β * adamMoment β g t + (1 - β) * g (t + 1)

/-- With a constant input `c`, the moving average after `t` steps is (1 − βᵗ) c. -/
theorem adam_moment_constant (β c : ℝ) (t : ℕ) :
    adamMoment β (fun _ => c) t = (1 - β ^ t) * c := by
  induction t with
  | zero => simp [adamMoment]
  | succ t ih =>
    rw [adamMoment, ih]
    ring

/-- Eq. (2.7): dividing by 1 − βᵗ removes the bias toward zero exactly when the
input is constant, for every step t ≥ 1 and decay rate β in [0, 1). -/
theorem adam_bias_correction_constant (β c : ℝ) (t : ℕ) (hβ0 : 0 ≤ β) (hβ1 : β < 1)
    (ht : 1 ≤ t) : adamMoment β (fun _ => c) t / (1 - β ^ t) = c := by
  have hpow : β ^ t < 1 := pow_lt_one₀ hβ0 hβ1 (by omega)
  have hne : 1 - β ^ t ≠ 0 := by linarith
  rw [adam_moment_constant]
  field_simp

/-! ## Federated objective and FedAvg: Eqs. (2.8)--(2.9) -/

/-- Eq. (2.8): the weighted sum of local objectives equals the average loss
over the pooled records, when the client record sets are pairwise disjoint. -/
theorem fed_objective_eq_pooled {K I : Type*} [DecidableEq I] (clients : Finset K)
    (P : K → Finset I) (f : I → ℝ)
    (hdisj : (clients : Set K).PairwiseDisjoint P) :
    (∑ k ∈ clients, ((P k).card : ℝ) / (∑ j ∈ clients, ((P j).card : ℝ)) *
        ((1 / ((P k).card : ℝ)) * ∑ i ∈ P k, f i))
      = (1 / ((clients.biUnion P).card : ℝ)) * ∑ i ∈ clients.biUnion P, f i := by
  rw [Finset.card_biUnion hdisj, Finset.sum_biUnion hdisj, Nat.cast_sum, Finset.mul_sum]
  refine Finset.sum_congr rfl fun k _ => ?_
  by_cases hk : (P k).card = 0
  · have hempty : P k = ∅ := Finset.card_eq_zero.mp hk
    simp [hempty]
  · have hk' : ((P k).card : ℝ) ≠ 0 := by exact_mod_cast hk
    field_simp

/-- Eqs. (2.3) and (2.8): a penalty term common to all local objectives passes
through the weighted sum unchanged, because the weights sum to one. -/
theorem fed_objective_common_penalty {K : Type*} (clients : Finset K) (mass : K → ℝ)
    (hTotal : (∑ k ∈ clients, mass k) ≠ 0) (F : K → ℝ) (penalty : ℝ) :
    (∑ k ∈ clients, mass k / (∑ j ∈ clients, mass j) * (F k + penalty))
      = (∑ k ∈ clients, mass k / (∑ j ∈ clients, mass j) * F k) + penalty := by
  simp only [mul_add]
  rw [Finset.sum_add_distrib, aggregate_identical_scalar clients mass hTotal penalty]

/-- Eq. (2.9): the FedAvg aggregate is a convex combination of the client
parameter vectors, so it lies in their convex hull. -/
theorem fedavg_mem_convexHull {K E : Type*} [AddCommGroup E] [Module ℝ E]
    (clients : Finset K) (m : K → ℕ) (w : K → E)
    (hTotal : 0 < ∑ k ∈ clients, (m k : ℝ)) :
    (∑ k ∈ clients, ((m k : ℝ) / ∑ j ∈ clients, (m j : ℝ)) • w k)
      ∈ convexHull ℝ (w '' (clients : Set K)) := by
  refine Convex.sum_mem (convex_convexHull ℝ _) ?_ ?_ ?_
  · intro k hk
    exact normalized_weight_nonnegative clients (fun k => (m k : ℝ))
      (fun k _ => Nat.cast_nonneg (m k)) hTotal k hk
  · exact normalized_weights_sum_one clients (fun k => (m k : ℝ)) hTotal.ne'
  · intro k hk
    exact subset_convexHull ℝ _ ⟨k, hk, rfl⟩

/-! ## Flow score as the maximum of fragment scores (Section 2.7, unit paragraph) and the
    monotonicity remark after Eq. (2.10); Eq. (2.10) itself is a definition and is not formalized -/

/-- The flow score is the maximum fragment score, and the alert condition is
S > τ. A flow is alerted exactly when some fragment score exceeds τ. -/
theorem flow_alert_iff_fragment_alert {ι : Type*} (fragments : Finset ι)
    (h : fragments.Nonempty) (score : ι → ℝ) (τ : ℝ) :
    τ < fragments.sup' h score ↔ ∃ i ∈ fragments, τ < score i :=
  Finset.lt_sup'_iff h

/-- A flow alerted at a threshold is alerted at every lower threshold. -/
theorem flow_alert_antitone {ι : Type*} (fragments : Finset ι)
    (h : fragments.Nonempty) (score : ι → ℝ) (τ τ' : ℝ) (hτ : τ ≤ τ')
    (hAlert : τ' < fragments.sup' h score) : τ < fragments.sup' h score :=
  lt_of_le_of_lt hτ hAlert

/-- Text after Eq. (2.10): raising τ cannot raise the number of alerted flows
in any fixed set, so recall and FPR, whose denominators do not depend on τ,
cannot rise. -/
theorem alert_rate_antitone {F : Type*} (flows : Finset F) (S : F → ℝ) (τ τ' : ℝ)
    (hτ : τ ≤ τ') :
    ((flows.filter fun x => τ' < S x).card : ℝ) / flows.card
      ≤ ((flows.filter fun x => τ < S x).card : ℝ) / flows.card := by
  have hsub : (flows.filter fun x => τ' < S x) ⊆ flows.filter fun x => τ < S x := by
    intro x hx
    rw [Finset.mem_filter] at hx ⊢
    exact ⟨hx.1, lt_of_le_of_lt hτ hx.2⟩
  have hcard : ((flows.filter fun x => τ' < S x).card : ℝ)
      ≤ ((flows.filter fun x => τ < S x).card : ℝ) := by
    exact_mod_cast Finset.card_le_card hsub
  exact div_le_div_of_nonneg_right hcard (Nat.cast_nonneg _)

/-! ## Threshold rule: Eq. (2.11) -/

/-- The rank of Eq. (2.11). -/
noncomputable def rank (α : ℝ) (n : ℕ) : ℕ := max 1 ⌈(1 - α) * (n : ℝ)⌉₊

/-- For ordered scores, at most n − k scores exceed the k-th one (k = i + 1). -/
theorem sorted_exceed_count_le {n : ℕ} (T : Fin n → ℝ) (hT : Monotone T) (i : Fin n) :
    (Finset.univ.filter fun j => T i < T j).card ≤ n - (i.val + 1) := by
  have hsub : (Finset.univ.filter fun j => T i < T j) ⊆ Finset.Ioi i := by
    intro j hj
    rw [Finset.mem_filter] at hj
    rw [Finset.mem_Ioi]
    by_contra hnot
    exact absurd (hT (not_lt.mp hnot)) (not_le.mpr hj.2)
  have hcard := Finset.card_le_card hsub
  rw [Fin.card_Ioi] at hcard
  omega

/-- The same count for scores given in any order, with the order statistic
T₍ₖ₎ obtained by sorting (k = i + 1). -/
theorem order_statistic_exceed_count_le {n : ℕ} (s : Fin n → ℝ) (i : Fin n) :
    (Finset.univ.filter fun j => s (Tuple.sort s i) < s j).card ≤ n - (i.val + 1) := by
  have hbij : (Finset.univ.filter fun j => s (Tuple.sort s i) < s j).card
      = (Finset.univ.filter fun j => (s ∘ Tuple.sort s) i < (s ∘ Tuple.sort s) j).card := by
    symm
    refine Finset.card_bij (fun j _ => Tuple.sort s j) ?_ ?_ ?_
    · intro j hj
      simpa using hj
    · intro a _ b _ hab
      exact (Tuple.sort s).injective hab
    · intro b hb
      refine ⟨(Tuple.sort s).symm b, ?_, by simp⟩
      simpa using hb
  rw [hbij]
  exact sorted_exceed_count_le (s ∘ Tuple.sort s) (Tuple.monotone_sort s) i

/-- Eq. (2.11): the rank is a valid index, and n − k ≤ α n. -/
theorem rank_bounds (α : ℝ) (n : ℕ) (hα : 0 ≤ α) (hn : 1 ≤ n) :
    1 ≤ rank α n ∧ rank α n ≤ n ∧ (n : ℝ) - (rank α n : ℝ) ≤ α * (n : ℝ) := by
  have hn0 : (0 : ℝ) ≤ (n : ℝ) := Nat.cast_nonneg n
  refine ⟨le_max_left _ _, ?_, ?_⟩
  · refine max_le hn (Nat.ceil_le.mpr ?_)
    nlinarith
  · have h1 : (1 - α) * (n : ℝ) ≤ (⌈(1 - α) * (n : ℝ)⌉₊ : ℝ) := Nat.le_ceil _
    have h2 : (⌈(1 - α) * (n : ℝ)⌉₊ : ℝ) ≤ (rank α n : ℝ) := by
      exact_mod_cast le_max_right 1 ⌈(1 - α) * (n : ℝ)⌉₊
    linarith

/-- Text after Eq. (2.11): with τ = T₍ₖ₎ and k from Eq. (2.11), the fraction
of calibration scores that exceed τ is at most α. -/
theorem calibration_empirical_fpr_le {n : ℕ} (s : Fin n → ℝ) (α : ℝ) (hα : 0 ≤ α)
    (hn : 1 ≤ n) (hk : rank α n - 1 < n) :
    ((Finset.univ.filter fun j => s (Tuple.sort s ⟨rank α n - 1, hk⟩) < s j).card : ℝ)
      / (n : ℝ) ≤ α := by
  obtain ⟨h1, h2, h3⟩ := rank_bounds α n hα hn
  have hcount := order_statistic_exceed_count_le s ⟨rank α n - 1, hk⟩
  have hidx : n - (rank α n - 1 + 1) = n - rank α n := by omega
  simp only [hidx] at hcount
  have hreal : ((Finset.univ.filter fun j =>
      s (Tuple.sort s ⟨rank α n - 1, hk⟩) < s j).card : ℝ) ≤ (n : ℝ) - (rank α n : ℝ) := by
    have : ((Finset.univ.filter fun j =>
        s (Tuple.sort s ⟨rank α n - 1, hk⟩) < s j).card : ℝ) ≤ ((n - rank α n : ℕ) : ℝ) := by
      exact_mod_cast hcount
    rwa [Nat.cast_sub h2] at this
  have hnpos : (0 : ℝ) < (n : ℝ) := by exact_mod_cast hn
  rw [div_le_iff₀ hnpos]
  linarith

/-! ## Violation bound and sample size: Eq. (2.12) -/

/-- The bound v(k) of Eq. (2.12). -/
noncomputable def violationBound (α : ℝ) (n k : ℕ) : ℝ :=
  ∑ j ∈ Finset.Icc k n, (n.choose j : ℝ) * (1 - α) ^ j * α ^ (n - j)

/-- v(0) = 1: the summands of Eq. (2.12) are the full binomial distribution. -/
theorem violationBound_zero (α : ℝ) (n : ℕ) : violationBound α n 0 = 1 := by
  have h := add_pow (1 - α) α n
  have hIcc : Finset.Icc 0 n = Finset.range (n + 1) := by
    ext j
    simp [Finset.mem_Icc, Finset.mem_range]
  unfold violationBound
  rw [hIcc]
  calc ∑ j ∈ Finset.range (n + 1), (n.choose j : ℝ) * (1 - α) ^ j * α ^ (n - j)
      = ∑ j ∈ Finset.range (n + 1), (1 - α) ^ j * α ^ (n - j) * (n.choose j : ℝ) :=
        Finset.sum_congr rfl fun j _ => by ring
    _ = (1 - α + α) ^ n := h.symm
    _ = 1 := by norm_num

/-- v(k) does not increase as the rank k grows, for α in [0, 1]. -/
theorem violationBound_antitone (α : ℝ) (n : ℕ) (hα0 : 0 ≤ α) (hα1 : α ≤ 1) :
    Antitone (violationBound α n) := by
  intro k k' hkk'
  unfold violationBound
  refine Finset.sum_le_sum_of_subset_of_nonneg (Finset.Icc_subset_Icc_left hkk') ?_
  intro j _ _
  have : (0 : ℝ) ≤ 1 - α := by linarith
  positivity

/-- At the largest rank, v(n) = (1 − α)ⁿ. -/
theorem violationBound_top (α : ℝ) (n : ℕ) : violationBound α n n = (1 - α) ^ n := by
  unfold violationBound
  simp

/-- A rank k in 1..n with v(k) ≤ δ exists exactly when (1 − α)ⁿ ≤ δ. -/
theorem exists_rank_iff_pow_le (α δ : ℝ) (n : ℕ) (hα0 : 0 ≤ α) (hα1 : α ≤ 1)
    (hn : 1 ≤ n) :
    (∃ k, 1 ≤ k ∧ k ≤ n ∧ violationBound α n k ≤ δ) ↔ (1 - α) ^ n ≤ δ := by
  constructor
  · rintro ⟨k, _, hkn, hv⟩
    have h := violationBound_antitone α n hα0 hα1 hkn
    rw [violationBound_top] at h
    exact h.trans hv
  · intro h
    exact ⟨n, hn, le_rfl, by rw [violationBound_top]; exact h⟩

/-- The sample-size condition of Section 2.7: (1 − α)ⁿ ≤ δ is the same as
n ≥ log δ / log(1 − α), for 0 < α < 1 and δ > 0. -/
theorem pow_le_iff_sample_size (α δ : ℝ) (n : ℕ) (hα0 : 0 < α) (hα1 : α < 1)
    (hδ : 0 < δ) :
    (1 - α) ^ n ≤ δ ↔ Real.log δ / Real.log (1 - α) ≤ (n : ℝ) := by
  have hbase : 0 < 1 - α := by linarith
  have hlog : Real.log (1 - α) < 0 := Real.log_neg hbase (by linarith)
  rw [div_le_iff_of_neg hlog, ← Real.log_pow,
    Real.log_le_log_iff (pow_pos hbase n) hδ]

set_option exponentiation.threshold 400 in
/-- The arithmetic behind "at least 299 benign flows": 0.99²⁹⁹ ≤ 0.05 < 0.99²⁹⁸. -/
theorem sample_size_299_arithmetic :
    (0.99 : ℝ) ^ 299 ≤ 0.05 ∧ (0.05 : ℝ) < 0.99 ^ 298 := by
  constructor <;> norm_num

/-- With α = 0.01 and δ = 0.05, a rank with v(k) ≤ δ exists exactly when
n ≥ 299. -/
theorem min_sample_size_299 (n : ℕ) :
    (∃ k, 1 ≤ k ∧ k ≤ n ∧ violationBound 0.01 n k ≤ 0.05) ↔ 299 ≤ n := by
  obtain ⟨h299, h298⟩ := sample_size_299_arithmetic
  have hbase : (1 : ℝ) - 0.01 = 0.99 := by norm_num
  constructor
  · rintro ⟨k, hk1, hkn, hv⟩
    have hn : 1 ≤ n := hk1.trans hkn
    have hpow := (exists_rank_iff_pow_le 0.01 0.05 n (by norm_num) (by norm_num) hn).mp
      ⟨k, hk1, hkn, hv⟩
    rw [hbase] at hpow
    by_contra hlt
    have hle : n ≤ 298 := by omega
    have hmono : (0.99 : ℝ) ^ 298 ≤ 0.99 ^ n :=
      pow_le_pow_of_le_one (by norm_num) (by norm_num) hle
    exact absurd (h298.trans_le (hmono.trans hpow)) (lt_irrefl _)
  · intro hn
    have hn1 : 1 ≤ n := by omega
    refine (exists_rank_iff_pow_le 0.01 0.05 n (by norm_num) (by norm_num) hn1).mpr ?_
    rw [hbase]
    have hmono : (0.99 : ℝ) ^ n ≤ 0.99 ^ 299 :=
      pow_le_pow_of_le_one (by norm_num) (by norm_num) hn
    exact hmono.trans h299

/-- "Generally higher", at n = 299, α = 0.01, δ = 0.05: Eq. (2.11) gives rank
297, while v(297) and v(298) exceed δ and only rank 299 meets v(k) ≤ δ. -/
theorem rank_299_example :
    rank 0.01 299 = 297 ∧ (0.05 : ℝ) < violationBound 0.01 299 297 ∧
    (0.05 : ℝ) < violationBound 0.01 299 298 ∧ violationBound 0.01 299 299 ≤ 0.05 := by
  obtain ⟨h299, h298⟩ := sample_size_299_arithmetic
  have hbase : (1 : ℝ) - 0.01 = 0.99 := by norm_num
  have hv298 : (0.05 : ℝ) < violationBound 0.01 299 298 := by
    have hterm : (Nat.choose 299 298 : ℝ) * (1 - 0.01) ^ 298 * 0.01 ^ (299 - 298)
        ≤ violationBound 0.01 299 298 := by
      unfold violationBound
      refine Finset.single_le_sum (f := fun j => (Nat.choose 299 j : ℝ) * (1 - 0.01) ^ j
        * 0.01 ^ (299 - j)) ?_ (by simp)
      intro j _
      positivity
    have hchoose : Nat.choose 299 298 = 299 := Nat.choose_succ_self_right 298
    have hone : (0.01 : ℝ) ^ (299 - 298) = 0.01 := by norm_num
    rw [hchoose, hbase, hone, Nat.cast_ofNat] at hterm
    generalize (0.99 : ℝ) ^ 298 = X at h298 hterm
    linarith
  refine ⟨?_, ?_, hv298, ?_⟩
  · unfold rank
    have hceil : ⌈(1 - (0.01 : ℝ)) * ((299 : ℕ) : ℝ)⌉₊ = 297 := by
      rw [Nat.ceil_eq_iff (by norm_num)]
      constructor <;> norm_num
    rw [hceil]
    rfl
  · have hanti := violationBound_antitone 0.01 299 (by norm_num) (by norm_num)
      (show 297 ≤ 298 by norm_num)
    linarith
  · rw [violationBound_top, hbase]
    exact h299

/-- Combinatorial core of the argument behind Eq. (2.12). For a set `A` of
scores that is closed downward, the order statistic T₍ₖ₎ (k = i + 1) lies in
`A` exactly when at least k of the n scores lie in `A`. -/
theorem order_statistic_mem_lower_iff {n : ℕ} (s : Fin n → ℝ) (A : ℝ → Prop)
    [DecidablePred A] (hA : ∀ x, A x → ∀ y, y ≤ x → A y) (i : Fin n) :
    A (s (Tuple.sort s i)) ↔ i.val + 1 ≤ (Finset.univ.filter fun j => A (s j)).card := by
  have hmono := Tuple.monotone_sort s
  have hbij : (Finset.univ.filter fun j => A (s j)).card
      = (Finset.univ.filter fun j => A ((s ∘ Tuple.sort s) j)).card := by
    symm
    refine Finset.card_bij (fun j _ => Tuple.sort s j) ?_ ?_ ?_
    · intro j hj
      simpa using hj
    · intro a _ b _ hab
      exact (Tuple.sort s).injective hab
    · intro b hb
      refine ⟨(Tuple.sort s).symm b, ?_, by simp⟩
      simpa using hb
  rw [hbij]
  constructor
  · intro hi
    have hsub : Finset.Iic i ⊆ Finset.univ.filter fun j => A ((s ∘ Tuple.sort s) j) := by
      intro j hj
      rw [Finset.mem_Iic] at hj
      rw [Finset.mem_filter]
      exact ⟨Finset.mem_univ j, hA _ hi _ (hmono hj)⟩
    have hcard := Finset.card_le_card hsub
    rwa [Fin.card_Iic] at hcard
  · intro hcard
    by_contra hi
    have hsub : (Finset.univ.filter fun j => A ((s ∘ Tuple.sort s) j)) ⊆ Finset.Iio i := by
      intro j hj
      rw [Finset.mem_filter] at hj
      rw [Finset.mem_Iio]
      by_contra hnot
      exact hi (hA _ hj.2 _ (hmono (not_lt.mp hnot)))
    have hle := Finset.card_le_card hsub
    rw [Fin.card_Iio] at hle
    omega

/-! ## Two-counter aliasing: Section 2.2 and the RQ4 input decision -/

/-- Section 2.2: two records with the same two counters receive the same score
from every model that reads only the two counters. -/
theorem aliasing_pointwise {Flow : Type*} (counters : Flow → ℕ × ℕ) (g : ℕ × ℕ → ℝ)
    (x y : Flow) (h : counters x = counters y) : g (counters x) = g (counters y) :=
  congrArg g h

/-- The matched example: one 60-octet TCP SYN packet (20 IP + 20 TCP + 20
option octets) and one 60-octet UDP datagram (20 IP + 8 UDP + 32 payload
octets) give the same counter pair (1, 60). -/
theorem aliasing_syn_udp_example :
    ((1, 20 + 20 + 20) : ℕ × ℕ) = (1, 60) ∧ ((1, 20 + 8 + 32) : ℕ × ℕ) = (1, 60) := by
  constructor <;> rfl

/-- If two flow classes have the same multiset of counter values, every
classifier that is a function of the counters gives them the same multiset of
scores. -/
theorem aliasing_score_multiset {Flow C : Type*} (counters : Flow → C) (g : C → ℝ)
    (A B : Multiset Flow) (h : A.map counters = B.map counters) :
    A.map (g ∘ counters) = B.map (g ∘ counters) := by
  rw [← Multiset.map_map, ← Multiset.map_map, h]

/-- Under the same hypothesis, every threshold alerts the same fraction of both
classes, so the true-positive rate equals the false-positive rate. -/
theorem aliasing_equal_alert_rates {Flow C : Type*} (counters : Flow → C) (g : C → ℝ)
    (A B : Multiset Flow) (h : A.map counters = B.map counters) (τ : ℝ) :
    (((A.map (g ∘ counters)).countP (fun v => τ < v) : ℕ) : ℝ) / (A.card : ℝ)
      = (((B.map (g ∘ counters)).countP (fun v => τ < v) : ℕ) : ℝ) / (B.card : ℝ) := by
  have hcard : A.card = B.card := by
    have := congrArg Multiset.card h
    simpa using this
  rw [aliasing_score_multiset counters g A B h, hcard]

/-- If every flow of both classes has the same counter value `p`, as in the
matched design, a threshold alerts either every flow of both classes or none. -/
theorem aliasing_constant_all_or_none {Flow C : Type*} (counters : Flow → C)
    (g : C → ℝ) (A B : Multiset Flow) (p : C)
    (hA : ∀ x ∈ A, counters x = p) (hB : ∀ x ∈ B, counters x = p) (τ : ℝ) :
    (∀ x ∈ A + B, τ < g (counters x)) ∨ (∀ x ∈ A + B, ¬ τ < g (counters x)) := by
  have hp : ∀ x ∈ A + B, counters x = p := by
    intro x hx
    rcases Multiset.mem_add.mp hx with hx | hx
    · exact hA x hx
    · exact hB x hx
  by_cases hτ : τ < g p
  · left
    intro x hx
    rw [hp x hx]
    exact hτ
  · right
    intro x hx
    rw [hp x hx]
    exact hτ

/-- Measure form: if the counters have the same distribution under two flow
distributions, every counter-based classifier alerts with the same
probability under both, at every threshold. -/
theorem aliasing_equal_alert_probability {Flow C : Type*} [MeasurableSpace Flow]
    [MeasurableSpace C] (μ ν : MeasureTheory.Measure Flow) (counters : Flow → C)
    (hc : Measurable counters) (g : C → ℝ) (τ : ℝ)
    (hg : MeasurableSet {p | τ < g p})
    (h : μ.map counters = ν.map counters) :
    μ {x | τ < g (counters x)} = ν {x | τ < g (counters x)} := by
  have hμ := MeasureTheory.Measure.map_apply (μ := μ) hc hg
  have hν := MeasureTheory.Measure.map_apply (μ := ν) hc hg
  rw [h] at hμ
  exact (hμ.symm.trans hν)

end ThesisVerification.Foundations

#print axioms ThesisVerification.Foundations.sigmoid_between
#print axioms ThesisVerification.Foundations.sigmoid_strictMono
#print axioms ThesisVerification.Foundations.logit_threshold_iff_sigmoid_threshold
#print axioms ThesisVerification.Foundations.bce_closed_form
#print axioms ThesisVerification.Foundations.bce_eq_logloss
#print axioms ThesisVerification.Foundations.hasDerivAt_bce
#print axioms ThesisVerification.Foundations.hasDerivAt_bce_coordinate
#print axioms ThesisVerification.Foundations.hasDerivAt_objective_coordinate
#print axioms ThesisVerification.Foundations.bce_convex
#print axioms ThesisVerification.Foundations.lrObjective_convex
#print axioms ThesisVerification.Foundations.parameter_counts
#print axioms ThesisVerification.Foundations.sampling_miss_single_packet
#print axioms ThesisVerification.Foundations.sgd_step_descent_scalar
#print axioms ThesisVerification.Foundations.adam_moment_constant
#print axioms ThesisVerification.Foundations.adam_bias_correction_constant
#print axioms ThesisVerification.Foundations.fed_objective_eq_pooled
#print axioms ThesisVerification.Foundations.fed_objective_common_penalty
#print axioms ThesisVerification.Foundations.fedavg_mem_convexHull
#print axioms ThesisVerification.Foundations.flow_alert_iff_fragment_alert
#print axioms ThesisVerification.Foundations.flow_alert_antitone
#print axioms ThesisVerification.Foundations.alert_rate_antitone
#print axioms ThesisVerification.Foundations.sorted_exceed_count_le
#print axioms ThesisVerification.Foundations.order_statistic_exceed_count_le
#print axioms ThesisVerification.Foundations.rank_bounds
#print axioms ThesisVerification.Foundations.calibration_empirical_fpr_le
#print axioms ThesisVerification.Foundations.violationBound_zero
#print axioms ThesisVerification.Foundations.violationBound_antitone
#print axioms ThesisVerification.Foundations.violationBound_top
#print axioms ThesisVerification.Foundations.exists_rank_iff_pow_le
#print axioms ThesisVerification.Foundations.pow_le_iff_sample_size
#print axioms ThesisVerification.Foundations.sample_size_299_arithmetic
#print axioms ThesisVerification.Foundations.min_sample_size_299
#print axioms ThesisVerification.Foundations.rank_299_example
#print axioms ThesisVerification.Foundations.order_statistic_mem_lower_iff
#print axioms ThesisVerification.Foundations.aliasing_pointwise
#print axioms ThesisVerification.Foundations.aliasing_syn_udp_example
#print axioms ThesisVerification.Foundations.aliasing_score_multiset
#print axioms ThesisVerification.Foundations.aliasing_equal_alert_rates
#print axioms ThesisVerification.Foundations.aliasing_constant_all_or_none
#print axioms ThesisVerification.Foundations.aliasing_equal_alert_probability
