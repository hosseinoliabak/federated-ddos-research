module

public import Mathlib.Algebra.BigOperators.Field
public import Mathlib.Basic.Real.Basic

public section

set_option warningAsError true

/-!
Elementary checks for normalized dataset-size weighting.
These are algebraic lemmas over exact real numbers, not proofs of training
convergence, floating-point implementation correctness, or measured speedup.
The denominator here is the total mass of the same finite client set s.
-/

namespace ThesisVerification

open scoped BigOperators

/-- Normalized masses sum to one when their total is nonzero. -/
theorem normalized_weights_sum_one {ι : Type*} (s : Finset ι) (mass : ι → ℝ)
    (hTotal : (∑ k ∈ s, mass k) ≠ 0) :
    (∑ k ∈ s, mass k / (∑ j ∈ s, mass j)) = 1 := by
  rw [← Finset.sum_div]
  exact div_self hTotal

/-- Nonnegative masses produce nonnegative weights when total mass is positive. -/
theorem normalized_weight_nonnegative {ι : Type*} (s : Finset ι) (mass : ι → ℝ)
    (hMass : ∀ k ∈ s, 0 ≤ mass k)
    (hTotal : 0 < ∑ j ∈ s, mass j) (k : ι) (hk : k ∈ s) :
    0 ≤ mass k / (∑ j ∈ s, mass j) := by
  exact div_nonneg (hMass k hk) (le_of_lt hTotal)

/-- Aggregating identical scalar parameters preserves their common value. -/
theorem aggregate_identical_scalar {ι : Type*} (s : Finset ι) (mass : ι → ℝ)
    (hTotal : (∑ k ∈ s, mass k) ≠ 0) (value : ℝ) :
    (∑ k ∈ s, (mass k / (∑ j ∈ s, mass j)) * value) = value := by
  rw [← Finset.sum_mul, normalized_weights_sum_one s mass hTotal, one_mul]

end ThesisVerification

#print axioms ThesisVerification.normalized_weights_sum_one
#print axioms ThesisVerification.normalized_weight_nonnegative
#print axioms ThesisVerification.aggregate_identical_scalar
