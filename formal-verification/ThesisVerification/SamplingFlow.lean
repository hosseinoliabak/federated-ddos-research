module

public import Mathlib.Algebra.BigOperators.Field
public import Mathlib.Basic.Real.Basic
public import Mathlib.Tactic.Linarith
public import ThesisVerification.Sampling

public section

set_option warningAsError true

/-!
Source: the controlled-track section of the thesis (review finding 6 of
`ch-controlled-track-draft-20261115/REVIEWS-20261115.md`), which separates the
per-record recall ceiling of `ThesisVerification/Sampling.lean` from the
flow-level combination of Chapter 2, where the score of a flow is the maximum
of the scores of its records (fragments) and one alert decision is made for
each flow. `SamplingFlow-source-map.json` gives the locator, meaning,
assumptions, and scope of every theorem.

A *unit* below is a flow or an episode: a nonempty finite set of records. The
per-record score `g` is a function of the record key, the unit score is the
maximum of the per-record scores, and the rule is deterministic: it alerts on
a unit exactly when the unit score exceeds the threshold `τ`.

The statements are exact and data-free. They concern only attack units whose
records all lie on keys that benign traffic carries with mass above the
false-positive budget `α`. They say nothing about units with a record on any
other key, about rules that use the number of records of a unit (a sum or a
count), about randomized rules, or about any measured count or learned model.
-/

namespace ThesisVerification.SamplingFlow

open scoped BigOperators

/-! ## The maximum rule with the false-positive rate counted on benign records -/

/-- Record-level budget. Let `b x` be the benign record mass of key `x`, and
let the rule alert on a record exactly when its score `g (key)` exceeds `τ`,
with benign false-positive rate at most `α`. A unit whose records all lie on
keys of benign mass above `α` has a maximum score that does not exceed `τ`, so
the maximum rule does not alert on the unit. -/
theorem unit_max_no_alert_on_heavy_keys {K ι : Type*} [Fintype K] (b g : K → ℝ) (τ α : ℝ)
    (hb : ∀ x, 0 ≤ b x) (hfpr : ∑ x, (if τ < g x then b x else 0) ≤ α)
    (records : Finset ι) (hne : records.Nonempty) (key : ι → K)
    (hheavy : ∀ i ∈ records, α < b (key i)) :
    ¬ τ < records.sup' hne (fun i => g (key i)) := by
  rw [Finset.lt_sup'_iff]
  rintro ⟨i, hi, hlt⟩
  have hfpr' : ∑ x, (if (decide (τ < g x)) = true then b x else 0) ≤ α := by
    simpa using hfpr
  have h := Sampling.deterministic_no_alert_on_heavy_key b (fun x => decide (τ < g x)) α hb
    hfpr' (key i) (hheavy i hi)
  simp only [decide_eq_false_iff_not] at h
  exact h hlt

/-- Recall zero, record-level budget. If every record of every attack unit lies
on a key of benign record mass above `α`, the maximum rule alerts on no attack
unit, so its recall over the attack units is zero for any weights `a`. -/
theorem unit_max_recall_zero_record_fpr {K ι A : Type*} [Fintype K] [Fintype A]
    (b g : K → ℝ) (τ α : ℝ)
    (hb : ∀ x, 0 ≤ b x) (hfpr : ∑ x, (if τ < g x then b x else 0) ≤ α)
    (a : A → ℝ) (records : A → Finset ι) (hne : ∀ u, (records u).Nonempty) (key : ι → K)
    (hheavy : ∀ u, ∀ i ∈ records u, α < b (key i)) :
    ∑ u, (if τ < (records u).sup' (hne u) (fun i => g (key i)) then a u else 0) = 0 := by
  refine Finset.sum_eq_zero fun u _ => ?_
  rw [ite_eq_right (unit_max_no_alert_on_heavy_keys b g τ α hb hfpr (records u) (hne u) key
    (hheavy u))]

/-! ## The maximum rule with the false-positive rate counted on benign units

This is the convention of Chapter 2: the threshold is set from benign flow
scores, and the false-positive rate is the fraction of benign flows that are
flagged. -/

/-- Unit-level budget. Let `w v` be the mass of benign unit `v`, and let the
maximum rule have benign unit false-positive rate at most `α`. If the benign
units that contain a record with key `x` have total mass above `α`, the score
of key `x` does not exceed `τ`: an alert on key `x` would flag every one of
those benign units. -/
theorem unit_fpr_no_alert_on_carried_key {K ι V : Type*} [Fintype V] [DecidableEq K]
    (g : K → ℝ) (τ α : ℝ) (w : V → ℝ) (hw : ∀ v, 0 ≤ w v)
    (records : V → Finset ι) (hne : ∀ v, (records v).Nonempty) (key : ι → K)
    (hfpr : ∑ v, (if τ < (records v).sup' (hne v) (fun i => g (key i)) then w v else 0) ≤ α)
    (x : K) (hx : α < ∑ v, (if ∃ i ∈ records v, key i = x then w v else 0)) :
    g x ≤ τ := by
  by_contra hlt
  have hlt' : τ < g x := lt_of_not_ge hlt
  have hle : ∑ v, (if ∃ i ∈ records v, key i = x then w v else 0)
      ≤ ∑ v, (if τ < (records v).sup' (hne v) (fun i => g (key i)) then w v else 0) := by
    refine Finset.sum_le_sum fun v _ => ?_
    by_cases hc : ∃ i ∈ records v, key i = x
    · obtain ⟨i, hi, hkey⟩ := hc
      have halert : τ < (records v).sup' (hne v) (fun i => g (key i)) :=
        (Finset.lt_sup'_iff (hne v)).mpr ⟨i, hi, by rw [hkey]; exact hlt'⟩
      rw [ite_eq_left ⟨i, hi, hkey⟩, ite_eq_left halert]
    · rw [ite_eq_right hc]
      split_ifs
      · exact hw v
      · exact le_refl 0
  linarith

/-- Recall zero, unit-level budget. If every record of every attack unit lies
on a key that benign units of total mass above `α` also contain, the maximum
rule with benign unit false-positive rate at most `α` alerts on no attack
unit, so its recall over the attack units is zero for any weights `a`. -/
theorem unit_max_recall_zero_unit_fpr {K ι V A : Type*} [Fintype V] [Fintype A] [DecidableEq K]
    (g : K → ℝ) (τ α : ℝ) (key : ι → K) (w : V → ℝ) (hw : ∀ v, 0 ≤ w v)
    (bRecords : V → Finset ι) (hbne : ∀ v, (bRecords v).Nonempty)
    (hfpr : ∑ v, (if τ < (bRecords v).sup' (hbne v) (fun i => g (key i)) then w v else 0) ≤ α)
    (a : A → ℝ) (aRecords : A → Finset ι) (hane : ∀ u, (aRecords u).Nonempty)
    (hcarried : ∀ u, ∀ i ∈ aRecords u,
      α < ∑ v, (if ∃ j ∈ bRecords v, key j = key i then w v else 0)) :
    ∑ u, (if τ < (aRecords u).sup' (hane u) (fun i => g (key i)) then a u else 0) = 0 := by
  refine Finset.sum_eq_zero fun u _ => ?_
  have hno : ¬ τ < (aRecords u).sup' (hane u) (fun i => g (key i)) := by
    rw [Finset.lt_sup'_iff]
    rintro ⟨i, hi, hlt⟩
    have h := unit_fpr_no_alert_on_carried_key g τ α w hw bRecords hbne key hfpr (key i)
      (hcarried u i hi)
    linarith
  rw [ite_eq_right hno]

/-! ## Aggregates between the smallest and the largest per-record score -/

/-- On a unit whose records all carry the key `x`, every aggregate `S` that
lies between the smallest and the largest per-record score of the unit equals
the score of `x`. The maximum, the minimum, the mean, and every quantile are
such aggregates; a sum or a count is not. -/
theorem pure_unit_aggregate_eq {K ι : Type*} (g : K → ℝ) (records : Finset ι)
    (hne : records.Nonempty) (key : ι → K) (x : K) (hpure : ∀ i ∈ records, key i = x) (S : ℝ)
    (hlo : records.inf' hne (fun i => g (key i)) ≤ S)
    (hhi : S ≤ records.sup' hne (fun i => g (key i))) : S = g x := by
  have hsup : records.sup' hne (fun i => g (key i)) ≤ g x :=
    Finset.sup'_le hne _ fun i hi => by rw [hpure i hi]
  have hinf : g x ≤ records.inf' hne (fun i => g (key i)) :=
    Finset.le_inf' hne _ fun i hi => by rw [hpure i hi]
  linarith

/-- The mean of the per-record scores of a unit lies between the smallest and
the largest of them, so `pure_unit_aggregate_eq` covers the mean. -/
theorem unit_mean_between_min_and_max {ι : Type*} (records : Finset ι) (hne : records.Nonempty)
    (s : ι → ℝ) :
    records.inf' hne s ≤ (∑ i ∈ records, s i) / records.card ∧
      (∑ i ∈ records, s i) / records.card ≤ records.sup' hne s := by
  have hcard : (0 : ℝ) < records.card := by exact_mod_cast Finset.card_pos.mpr hne
  constructor
  · rw [le_div_iff₀ hcard]
    have h := Finset.card_nsmul_le_sum records s (records.inf' hne s)
      fun i hi => Finset.inf'_le s hi
    rw [nsmul_eq_mul] at h
    linarith
  · rw [div_le_iff₀ hcard]
    have h := Finset.sum_le_card_nsmul records s (records.sup' hne s)
      fun i hi => Finset.le_sup' s hi
    rw [nsmul_eq_mul] at h
    linarith

/-- Recall zero for an aggregate rule on one key. Let the unit score be any
aggregate between the smallest and the largest per-record score of the unit
(`Sb` on benign units, `Sa` on attack units), and let the rule alert on a unit
exactly when its score exceeds `τ`, with benign unit false-positive rate at
most `α`. If the benign units whose records all carry the key `x` have total
mass above `α`, the rule alerts on no attack unit whose records all carry `x`,
so its recall over such attack units is zero for any weights `a`. -/
theorem unit_aggregate_recall_zero_on_pure_key {K ι V A : Type*} [Fintype V] [Fintype A]
    [DecidableEq K] (g : K → ℝ) (τ α : ℝ) (key : ι → K) (x : K)
    (w : V → ℝ) (hw : ∀ v, 0 ≤ w v)
    (bRecords : V → Finset ι) (hbne : ∀ v, (bRecords v).Nonempty) (Sb : V → ℝ)
    (hSb_lo : ∀ v, (bRecords v).inf' (hbne v) (fun i => g (key i)) ≤ Sb v)
    (hSb_hi : ∀ v, Sb v ≤ (bRecords v).sup' (hbne v) (fun i => g (key i)))
    (hfpr : ∑ v, (if τ < Sb v then w v else 0) ≤ α)
    (hx : α < ∑ v, (if ∀ i ∈ bRecords v, key i = x then w v else 0))
    (a : A → ℝ) (aRecords : A → Finset ι) (hane : ∀ u, (aRecords u).Nonempty) (Sa : A → ℝ)
    (hSa_lo : ∀ u, (aRecords u).inf' (hane u) (fun i => g (key i)) ≤ Sa u)
    (hSa_hi : ∀ u, Sa u ≤ (aRecords u).sup' (hane u) (fun i => g (key i)))
    (hpure : ∀ u, ∀ i ∈ aRecords u, key i = x) :
    ∑ u, (if τ < Sa u then a u else 0) = 0 := by
  have hgx : g x ≤ τ := by
    by_contra hlt
    have hlt' : τ < g x := lt_of_not_ge hlt
    have hle : ∑ v, (if ∀ i ∈ bRecords v, key i = x then w v else 0)
        ≤ ∑ v, (if τ < Sb v then w v else 0) := by
      refine Finset.sum_le_sum fun v _ => ?_
      by_cases hc : ∀ i ∈ bRecords v, key i = x
      · have hS : Sb v = g x :=
          pure_unit_aggregate_eq g (bRecords v) (hbne v) key x hc (Sb v) (hSb_lo v) (hSb_hi v)
        have halert : τ < Sb v := by rw [hS]; exact hlt'
        rw [ite_eq_left hc, ite_eq_left halert]
      · rw [ite_eq_right hc]
        split_ifs
        · exact hw v
        · exact le_refl 0
    linarith
  refine Finset.sum_eq_zero fun u _ => ?_
  have hS : Sa u = g x :=
    pure_unit_aggregate_eq g (aRecords u) (hane u) key x (hpure u) (Sa u) (hSa_lo u) (hSa_hi u)
  have hno : ¬ τ < Sa u := by rw [hS]; exact not_lt.mpr hgx
  rw [ite_eq_right hno]

end ThesisVerification.SamplingFlow

#print axioms ThesisVerification.SamplingFlow.unit_max_no_alert_on_heavy_keys
#print axioms ThesisVerification.SamplingFlow.unit_max_recall_zero_record_fpr
#print axioms ThesisVerification.SamplingFlow.unit_fpr_no_alert_on_carried_key
#print axioms ThesisVerification.SamplingFlow.unit_max_recall_zero_unit_fpr
#print axioms ThesisVerification.SamplingFlow.pure_unit_aggregate_eq
#print axioms ThesisVerification.SamplingFlow.unit_mean_between_min_and_max
#print axioms ThesisVerification.SamplingFlow.unit_aggregate_recall_zero_on_pure_key
