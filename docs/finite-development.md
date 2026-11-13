The scalar control asks whether one stored predictor can rank the assigned labels without neural training or model exchange. Arp et al.(2022), P4/P6, motivates explanation and adequate simple baselines; this particular criterion is a study choice.

This is a historical pre-execution procedure note. See [source versions](finite-development-source-versions.md) for the current integration and the exact executed source. The original note is retained below.

`train_separability_diagnostic.two_u` counts benign/attack pairs exactly:2for an attack value above benign,1for a tie,0otherwise. `select_feature` maximizes that numerator or its reversed orientation. Equal integer criteria choose the first feature in the locked order; chance orientation is positive. The integer bound is checked before uint64 arithmetic. Constant features and single-class support are explicit. This establishes stored-label separability, not an extraction bug, spurious causation, physical episodes or operational detection.

`fit_local` requests only its owner's supervised TRAIN view. `fit_pooled` separately declares a raw TRAIN union and reuses the original byte-exact pooled application codec/roundtrips, retaining every source row/tail. Neither fits a transform or accesses validation. The immutable CSV-only scalar artifact binds the complete73feature schema, train identities/support, selected feature/direction and scope; its predictor-only API accepts no labels and rejects wrong owners/schema/hash/nonfinite input. Unknown physical units and live correspondence remain unknown.

`evaluate_validation` uses a frozen validation view only, joins reporting labels after identity-linked finite scores, and reports support/NA/ties and missing failures. It cannot choose a feature, threshold, calibration rule or optimizer. Scores are signed float64 stored values; they are not calibrated probabilities or a silent replacement for the original sigmoid32 neural convention. A partial failure raises an exception carrying exact counters; an acquired-data controller must retain this receipt and produce no successful seal.

Run the fabricated check with the locked environment:

```sh
python scripts/train_separability_diagnostic.py --synthetic
```

The CLI accepts no acquired-data paths. The private finite protocol proposes the existing SGD/Adam grid, two seeds,1/2/4checkpoints, independent-local own-validation selection versus declared union/federated feedback, a separate wider-family check and AF2000 sensitivity. That full neural/statistical search runner and acquired-data diagnostic launch controller are not implemented by this module. Both require finite caps, source/code/check bindings and parent procedure review before actual fitting. Existing completed runner/bundle artifacts remain unchanged.

Evidence: Arp et al.2022 §2.2/P4–P6; NumPy2.4 argsort stable, reduceat segment semantics and explicit integer-dtype overflow warning; scikit-learn1.9.0 binary positive class/ROC and noninterpolated AP. The exact Context7/RAG retrievals and current design proposal are preserved privately. No new dependency was added.
