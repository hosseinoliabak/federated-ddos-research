module

public import Mathlib.Basic.Complex.Basic
public import Mathlib.Order.Monotone.Basic
public import Mathlib.Tactic.Linarith
public import Mathlib.Tactic.NormNum

public section

set_option warningAsError true

/-!
Source: Sellier (2023), DOI 10.1002/ail2.89, equations (7)--(9),
and the best-solution recording step on page 10.

The differential equation is modeled pointwise: r, im, dtR, dtI, dxxR,
and dxxI stand for component values and their derivatives at one point.
This file checks the complex algebra; it does not establish existence,
regularity, boundary conditions, FDTD stability, or the learning results.
-/

namespace ThesisVerification.Sellier

/-- Pointwise algebra of Eq. (7), with Eq. (8)'s real/imaginary decomposition. -/
def schrodingerPoint (h m potential r im dtR dtI dxxR dxxI : ℝ) : Prop :=
  Complex.I * (h : ℂ) * Complex.mk dtR dtI =
    -((h ^ 2 / (2 * m) : ℝ) : ℂ) * Complex.mk dxxR dxxI +
      (potential : ℂ) * Complex.mk r im

/-- The two component equations algebraically equivalent to Eqs. (7) and (8). -/
theorem schrodinger_split (h m potential r im dtR dtI dxxR dxxI : ℝ) :
    schrodingerPoint h m potential r im dtR dtI dxxR dxxI ↔
      (h * dtR = -(h ^ 2 / (2 * m)) * dxxI + potential * im ∧
       h * dtI = (h ^ 2 / (2 * m)) * dxxR - potential * r) := by
  unfold schrodingerPoint
  rw [Complex.ext_iff]
  simp only [Complex.mul_re, Complex.mul_im, Complex.I_re, Complex.I_im,
    Complex.ofReal_re, Complex.ofReal_im,
    Complex.add_re, Complex.add_im, Complex.neg_re, Complex.neg_im,
    neg_zero, mul_zero, zero_mul, zero_sub, sub_zero, zero_add, add_zero, one_mul]
  constructor
  · rintro ⟨hReal, hImag⟩
    constructor
    · exact hImag
    · linarith
  · rintro ⟨hReal, hImag⟩
    constructor
    · linarith
    · exact hReal

/-- Solving for the derivatives requires a nonzero reduced Planck constant. -/
theorem schrodinger_derivatives (h m potential r im dtR dtI dxxR dxxI : ℝ)
    (hh : h ≠ 0) :
    schrodingerPoint h m potential r im dtR dtI dxxR dxxI ↔
      (dtR = (-(h ^ 2 / (2 * m)) * dxxI + potential * im) / h ∧
       dtI = ((h ^ 2 / (2 * m)) * dxxR - potential * r) / h) := by
  rw [schrodinger_split]
  constructor
  · rintro ⟨hR, hI⟩
    constructor
    · apply (eq_div_iff hh).2
      simpa only [mul_comm] using hR
    · apply (eq_div_iff hh).2
      simpa only [mul_comm] using hI
  · rintro ⟨hR, hI⟩
    constructor
    · simpa only [mul_comm] using (eq_div_iff hh).1 hR
    · simpa only [mul_comm] using (eq_div_iff hh).1 hI

/-- Literal algebraic transcription of the displayed Eq. (9), page 8. -/
def printedEq9 (h m potential r im dtR dtI dxxR dxxI : ℝ) : Prop :=
  dtR = -(h ^ 2 / (2 * m)) * dxxI + potential * im ∧
  dtI = -(h ^ 2 / (2 * m)) * dxxR - potential * r

/-- At h=m=1 and zero potential, printed Eq. (9) need not satisfy Eq. (7). -/
theorem printed_eq9_counterexample :
    printedEq9 1 1 0 0 0 0 (-1) 2 0 ∧
    ¬ schrodingerPoint 1 1 0 0 0 0 (-1) 2 0 := by
  constructor
  · norm_num [printedEq9]
  · rw [schrodinger_split]
    norm_num

/-- Mathematical model of recording the best objective value evaluated so far. -/
noncomputable def bestLoss (loss : ℕ → ℝ) : ℕ → ℝ
  | 0 => loss 0
  | n + 1 => min (bestLoss loss n) (loss (n + 1))

/-- The recorded best loss cannot increase, regardless of the candidate sequence. -/
theorem best_loss_antitone (loss : ℕ → ℝ) : Antitone (bestLoss loss) := by
  apply antitone_nat_of_succ_le
  intro n
  exact min_le_left _ _

/-- The recorded value is the loss of a candidate actually evaluated. -/
theorem best_loss_attained (loss : ℕ → ℝ) (n : ℕ) :
    ∃ k ≤ n, bestLoss loss n = loss k := by
  induction n with
  | zero => exact ⟨0, le_rfl, rfl⟩
  | succ n ih =>
    by_cases h : bestLoss loss n ≤ loss (n + 1)
    · obtain ⟨k, hk, hValue⟩ := ih
      refine ⟨k, Nat.le_succ_of_le hk, ?_⟩
      exact (min_eq_left h).trans hValue
    · exact ⟨n + 1, le_rfl, min_eq_right (le_of_not_ge h)⟩

end ThesisVerification.Sellier

#print axioms ThesisVerification.Sellier.schrodinger_split
#print axioms ThesisVerification.Sellier.schrodinger_derivatives
#print axioms ThesisVerification.Sellier.printed_eq9_counterexample
#print axioms ThesisVerification.Sellier.best_loss_antitone
#print axioms ThesisVerification.Sellier.best_loss_attained
