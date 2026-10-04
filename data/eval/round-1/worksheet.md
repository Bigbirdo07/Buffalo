# Blind adjudication worksheet

Assign a status to each atomic claim **from the evidence shown**. The
engine's own status, the rule it applied and its per-evidence verdicts are
deliberately withheld; they are in a separate answer key.

Record answers in `responses.json` (a template is generated alongside this
file). For each item:

- `reviewer_status`: one of `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONTEXT_DEPENDENT`, `INSUFFICIENT_EVIDENCE`, `CONTRADICTED`, `UNREVIEWED`
- `extraction_disputed`: `true` if you reject how the evidence was
  characterised (an effect label, a system description, the claim's scope)
  rather than disagreeing about the status it implies
- `note`: free text; most useful on any disagreement

Status definitions as the engine uses them:

| Status | Meaning |
| --- | --- |
| SUPPORTED | Direct evidence supports the claim, none refutes or qualifies it |
| PARTIALLY_SUPPORTED | Only qualified or partial direct support |
| CONTEXT_DEPENDENT | Direct evidence both supports and limits it: true in some contexts |
| INSUFFICIENT_EVIDENCE | Not enough direct evidence to judge |
| CONTRADICTED | Direct evidence refutes it, from independent publications |

Citation statuses you will see:

- `VERIFIED` — quoted span located in retrieved source text
- `UPSTREAM_ATTESTED` — identifier resolves, curator recorded the quote, but
  the text was not retrievable, so the quote is unconfirmed either way
- `SPAN_NOT_LOCATED` — text *was* retrieved and the quote is not in it

9 items, order deterministically shuffled.

---

## Item 1 — `SCAR20:ac1-lc3-flux-npc`

**Disease / gene:** SCAR20 / SNX14

**Upstream edge claim:** SNX14 Loss of Function contributes to Impaired Autophagosome Clearance in Neural Progenitors.

**Atomic claim to judge:** **SNX14 loss slows autophagic LC3 flux in patient-derived neural progenitor cells.**

**Scope**

- alleles: biallelic SNX14 loss-of-function
- allele class: biallelic loss-of-function
- cell type scope: patient neural progenitor cells
- disease scope: SCAR20
- readouts bearing on this claim: lc3_flux, lc3_ii_level
- readouts counted as this capability at all: lc3_flux, lc3_ii_level, autophagosome_lysosome_fusion, autolysosome_formation, autophagic_cargo_degradation

**Evidence (2 item(s))**

- **s01** · PMID:25848753
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: lc3_flux · effect as extracted: **decreased**
    - system: patient-derived neural progenitor cells, nutrient deprivation, leupeptin and ammonium chloride flux block
    - species: Homo sapiens · cell types: patient neural progenitor cells
    - alleles: biallelic SNX14 loss-of-function · disease entity: SCAR20
    - span (full_text): “By LC3 flux analysis in nutrient deprived conditions, where LC3II ratios in the presence and absence of lysosomal inhibitors (Leupeptin and NH 4 Cl) were calculated 20 , we identified slower LC3 flux in patient cells compared to controls.”
    - extractor note: Genuine flux measurement with lysosomal inhibitors, not inferred from steady-state LC3-II. This is the strongest support for the edge and it is specific to neural progenitors.

- **s02** · PMID:25848753
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: lc3_ii_level · effect as extracted: **decreased**
    - system: patient cells with genetic complementation by tagged SNX14
    - species: Homo sapiens · cell types: patient neural progenitor cells
    - alleles: biallelic SNX14 loss-of-function · disease entity: SCAR20
    - span (full_text): “Importantly, the increased LC3 II levels were recovered to basal rates by forced expression of tagged SNX14 into patient cells ( Fig. 4a ).”
    - extractor note: Genetic complementation: re-expression of SNX14 normalised elevated LC3-II, establishing SNX14 dependence of the readout. Same publication as s01, so not an independent source.

---

## Item 2 — `SCAR20:ac3-autolysosome-formation`

**Disease / gene:** SCAR20 / SNX14

**Upstream edge claim:** SNX14 Loss of Function contributes to Impaired Autophagosome Clearance in Neural Progenitors.

**Atomic claim to judge:** **SNX14 loss impairs autolysosome formation.**

**Scope**

- alleles: SNX14 knockout, biallelic SNX14 loss-of-function
- allele class: biallelic loss-of-function or knockout
- cell type scope: not scoped
- disease scope: SCAR20
- readouts bearing on this claim: autolysosome_formation
- readouts counted as this capability at all: lc3_flux, lc3_ii_level, autophagosome_lysosome_fusion, autolysosome_formation, autophagic_cargo_degradation

**Evidence (1 item(s))**

- **s04** · PMID:29635513 (upstream wrote `url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/`)
    - citation: **UPSTREAM_ATTESTED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: autolysosome_formation · effect as extracted: **unchanged**
    - system: SCAR20 patient fibroblasts, marker colocalisation and p62 degradation
    - species: Homo sapiens · cell types: patient fibroblasts
    - alleles: biallelic SNX14 loss-of-function · disease entity: SCAR20
    - span (upstream_curated_snippet): “we observe a very strong colocalization of autophagosome and lysosome associated markers indicating the efficient formation of autolysosomes in SCAR20 mutant fibroblasts”
    - extractor note: Preserved autolysosome formation in patient fibroblasts under the tested conditions. Patient cells, but a non-neural cell type. Full text is not open access.

---

## Item 3 — `SCAR16:ac5-ubox-other-missense`

**Disease / gene:** SCAR16 / STUB1

**Upstream edge claim:** Biallelic STUB1 Loss-of-Function Variants contributes to Loss of CHIP E3 Ubiquitin Ligase Activity.

**Atomic claim to judge:** **SCAR16 U-box missense alleles other than p.Thr246Met cause loss of CHIP E3 ubiquitin ligase activity.**

**Scope**

- alleles: p.Ser236Thr, p.Met240Thr
- allele class: U-box missense
- cell type scope: not scoped
- disease scope: SCAR16
- readouts bearing on this claim: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation
- readouts counted as this capability at all: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation

**Evidence (4 item(s))**

- **o08** · PMID:28396517
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **unchanged**
    - system: purified recombinant CHIP, in vitro ubiquitination, 37 C, 1 h
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Glu28Lys, p.Lys145Gln, p.Met211Ile, p.Ser236Thr · disease entity: SCAR16
    - span (full_text): “The ubiquitination activities of the other mutants (E28K, K145Q, M211I, and S236T) were not overtly different from WT CHIP.”
    - extractor note: Four of six tested disease alleles retain bulk ligase activity in this assay. This is the upstream REFUTE pointer already curated on the SCAR16 node.

- **o10** · PMID:29317501
    - citation: **VERIFIED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **partially_retained**
    - system: recombinant CHIP assayed below the mutants' melting temperature
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 mutant panel · disease entity: SCAR16
    - span (abstract): “Consistent with decreased CHIP stability promoting its dysfunction in SCAR16, most mutant proteins recovered activity when the assays were performed below the mutants' melting temperature.”
    - extractor note: Temperature dependence: the same alleles score as defective or near-normal depending on assay temperature. Panel alleles are not enumerated in this sentence, so this is class-level.

- **o11** · PMID:31619515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsp70_polyubiquitination · effect as extracted: **abolished**
    - system: recombinant CHIP panel across SCAR16 alleles
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Met240Thr, p.Thr246Met · disease entity: SCAR16
    - span (full_text): “Second, all mutant CHIP proteins maintained some capacity to polyubiquitinate HSP70 except for two Ubox mutants, M240T and T246M ( Fig. 3 E ).”
    - extractor note: Same sentence establishes the complement: every other tested SCAR16 allele retained some HSP70 polyubiquitination. Recorded separately as o12.

- **o15** · PMID:42567515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **abolished**
    - system: recombinant protein biochemistry and cellular models, 13 variants
    - species: Homo sapiens · cell types: not stated
    - alleles: U-box missense · disease entity: SCA48
    - span (abstract): “Conversely, U-box variants abolished ligase function, promoted the formation of high-molecular-weight oligomers, and often increased CHIP levels while only partially impairing co-chaperone activity.”
    - extractor note: Cross-entity (SCA48). Also reports temperature-sensitive defects across mutants.

---

## Item 4 — `SCAR20:ac2-fusion-block`

**Disease / gene:** SCAR20 / SNX14

**Upstream edge claim:** SNX14 Loss of Function contributes to Impaired Autophagosome Clearance in Neural Progenitors.

**Atomic claim to judge:** **SNX14 loss blocks autophagosome-lysosome fusion.**

**Scope**

- alleles: SNX14 knockout, biallelic SNX14 loss-of-function
- allele class: biallelic loss-of-function or knockout
- cell type scope: not scoped
- disease scope: SCAR20
- readouts bearing on this claim: autophagosome_lysosome_fusion
- readouts counted as this capability at all: lc3_flux, lc3_ii_level, autophagosome_lysosome_fusion, autolysosome_formation, autophagic_cargo_degradation

**Evidence (1 item(s))**

- **s03** · PMID:29635513 (upstream wrote `url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/`)
    - citation: **UPSTREAM_ATTESTED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: autophagosome_lysosome_fusion · effect as extracted: **unchanged**
    - system: HEK293 SNX14 knockout, tandem fluorescent LC3 reporter
    - species: Homo sapiens · cell types: HEK293
    - alleles: SNX14 knockout · disease entity: SCAR20
    - span (upstream_curated_snippet): “indicating that loss of SNX14 did not impact autophagosome-lysosome fusion”
    - extractor note: Refutes a general fusion block. Measured in HEK293, a non-neural line, so it constrains the fusion sub-step rather than the neural-progenitor clearance finding. Full text is not open access, so the results-section span cannot be located.

---

## Item 5 — `SCAR16:ac4-interdomain-missense`

**Disease / gene:** SCAR16 / STUB1

**Upstream edge claim:** Biallelic STUB1 Loss-of-Function Variants contributes to Loss of CHIP E3 Ubiquitin Ligase Activity.

**Atomic claim to judge:** **SCAR16 inter-domain/linker-region missense alleles cause loss of CHIP E3 ubiquitin ligase activity.**

**Scope**

- alleles: p.Lys145Gln, p.Met211Ile
- allele class: inter-domain/linker-region missense
- cell type scope: not scoped
- disease scope: SCAR16
- readouts bearing on this claim: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation
- readouts counted as this capability at all: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation

**Evidence (5 item(s))**

- **o04** · PMID:41851873
    - citation: **VERIFIED**, full text retrieved
    - origin: BACKGROUND_CITATION
    - readout: e3_ligase_activity · effect as extracted: **decreased**
    - system: not tested in this paper; introduction sentence citing an earlier study
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Lys145Gln · disease entity: SCAR16
    - span (full_text): “In addition, the STUB1 missense mutation p.(Lys145Gln) has been found to impair the ubiquitin ligase activity of CHIP [ 9 ].”
    - extractor note: Introduction sentence attributing the finding to its reference 9 (Kanack et al. 2018, PMID 29317501). Checked against that paper in o11.

- **o08** · PMID:28396517
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **unchanged**
    - system: purified recombinant CHIP, in vitro ubiquitination, 37 C, 1 h
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Glu28Lys, p.Lys145Gln, p.Met211Ile, p.Ser236Thr · disease entity: SCAR16
    - span (full_text): “The ubiquitination activities of the other mutants (E28K, K145Q, M211I, and S236T) were not overtly different from WT CHIP.”
    - extractor note: Four of six tested disease alleles retain bulk ligase activity in this assay. This is the upstream REFUTE pointer already curated on the SCAR16 node.

- **o10** · PMID:29317501
    - citation: **VERIFIED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **partially_retained**
    - system: recombinant CHIP assayed below the mutants' melting temperature
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 mutant panel · disease entity: SCAR16
    - span (abstract): “Consistent with decreased CHIP stability promoting its dysfunction in SCAR16, most mutant proteins recovered activity when the assays were performed below the mutants' melting temperature.”
    - extractor note: Temperature dependence: the same alleles score as defective or near-normal depending on assay temperature. Panel alleles are not enumerated in this sentence, so this is class-level.

- **o12** · PMID:31619515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsp70_polyubiquitination · effect as extracted: **partially_retained**
    - system: recombinant CHIP panel across SCAR16 alleles
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 mutant panel · disease entity: SCAR16
    - span (full_text): “Second, all mutant CHIP proteins maintained some capacity to polyubiquitinate HSP70 except for two Ubox mutants, M240T and T246M ( Fig. 3 E ).”
    - extractor note: Class-level complement of o11: non-U-box SCAR16 alleles retain measurable substrate polyubiquitination. Alleles are not named in this sentence.

- **o13** · PMID:31619515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: polyubiquitin_chain_formation · effect as extracted: **unchanged**
    - system: recombinant CHIP panel, E2-dependent chain formation
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 non-U-box panel · disease entity: SCAR16
    - span (full_text): “Third, all Ubox mutants had a reduced capacity to form polyubiquitin chains, perhaps due to altered interactions with E2 enzymes, whereas TPR and CC mutations were not defective in these same conditions ( Fig. 3 F ).”
    - extractor note: TPR and coiled-coil alleles show no chain-formation defect under these conditions, while all U-box alleles do.

---

## Item 6 — `SCAR16:ac2-pre-ubox-truncation`

**Disease / gene:** SCAR16 / STUB1

**Upstream edge claim:** Biallelic STUB1 Loss-of-Function Variants contributes to Loss of CHIP E3 Ubiquitin Ligase Activity.

**Atomic claim to judge:** **The truncating STUB1 allele p.Gln118*, which removes the U-box, causes loss of CHIP E3 ubiquitin ligase activity.**

**Scope**

- alleles: p.Gln118*
- allele class: pre-U-box truncation
- cell type scope: not scoped
- disease scope: SCAR16
- readouts bearing on this claim: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation
- readouts counted as this capability at all: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation

**Evidence (1 item(s))**

- **o02** · PMID:41851873
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsc70_ubiquitination · effect as extracted: **decreased**
    - system: HEK293T transient overexpression with immunoprecipitation
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Gln118* · disease entity: SCAR16
    - span (full_text): “The results demonstrated that this truncation mutant exhibited significantly reduced ubiquitination activity toward Hsc70, with markedly decreased Hsc70 polyubiquitination compared to that of wild-type STUB1 (Fig. 3 C-E).”

---

## Item 7 — `SCAR16:ac3-tpr-missense`

**Disease / gene:** SCAR16 / STUB1

**Upstream edge claim:** Biallelic STUB1 Loss-of-Function Variants contributes to Loss of CHIP E3 Ubiquitin Ligase Activity.

**Atomic claim to judge:** **SCAR16 TPR-domain missense alleles cause loss of CHIP E3 ubiquitin ligase activity.**

**Scope**

- alleles: p.Glu28Lys, p.Asn65Ser
- allele class: TPR-domain missense
- cell type scope: not scoped
- disease scope: SCAR16
- readouts bearing on this claim: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation
- readouts counted as this capability at all: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation

**Evidence (8 item(s))**

- **o07** · PMID:28396517
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsc70_ubiquitination · effect as extracted: **processivity_defect**
    - system: purified recombinant CHIP, in vitro ubiquitination, 37 C, 1 h
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Asn65Ser · disease entity: SCAR16
    - span (full_text): “Hsc70 seemed to be mono-ubiquitinated by the N65S mutant, while no Hsc70-ubiquitination was detected for T246M, confirming previous findings on these two variants [ 3 , 9 ].”
    - extractor note: Hsc70 chain elongation is reduced to mono-ubiquitination while CHIP self-ubiquitination is retained. This is a processivity/readout-specific defect; the experiment does not compare multiple substrates and therefore does not establish substrate selectivity.

- **o08** · PMID:28396517
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **unchanged**
    - system: purified recombinant CHIP, in vitro ubiquitination, 37 C, 1 h
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Glu28Lys, p.Lys145Gln, p.Met211Ile, p.Ser236Thr · disease entity: SCAR16
    - span (full_text): “The ubiquitination activities of the other mutants (E28K, K145Q, M211I, and S236T) were not overtly different from WT CHIP.”
    - extractor note: Four of six tested disease alleles retain bulk ligase activity in this assay. This is the upstream REFUTE pointer already curated on the SCAR16 node.

- **o09** · PMID:25258038
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsc70_ubiquitination · effect as extracted: **processivity_defect**
    - system: in vitro ubiquitination of HSC70
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Asn65Ser · disease entity: SCAR16
    - span (abstract): “We show that the p.Asn65Ser substitution impairs CHIP's ability to ubiquitinate HSC70 in vitro, despite being able to self-ubiquitinate.”
    - extractor note: Independent replication of impaired HSC70 ubiquitination with retained self-ubiquitination. These are distinct readouts; without a multi-substrate comparison this is coded as a processivity/readout-specific defect, not substrate selectivity.

- **o10** · PMID:29317501
    - citation: **VERIFIED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **partially_retained**
    - system: recombinant CHIP assayed below the mutants' melting temperature
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 mutant panel · disease entity: SCAR16
    - span (abstract): “Consistent with decreased CHIP stability promoting its dysfunction in SCAR16, most mutant proteins recovered activity when the assays were performed below the mutants' melting temperature.”
    - extractor note: Temperature dependence: the same alleles score as defective or near-normal depending on assay temperature. Panel alleles are not enumerated in this sentence, so this is class-level.

- **o12** · PMID:31619515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsp70_polyubiquitination · effect as extracted: **partially_retained**
    - system: recombinant CHIP panel across SCAR16 alleles
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 mutant panel · disease entity: SCAR16
    - span (full_text): “Second, all mutant CHIP proteins maintained some capacity to polyubiquitinate HSP70 except for two Ubox mutants, M240T and T246M ( Fig. 3 E ).”
    - extractor note: Class-level complement of o11: non-U-box SCAR16 alleles retain measurable substrate polyubiquitination. Alleles are not named in this sentence.

- **o13** · PMID:31619515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: polyubiquitin_chain_formation · effect as extracted: **unchanged**
    - system: recombinant CHIP panel, E2-dependent chain formation
    - species: Homo sapiens · cell types: not stated
    - alleles: SCAR16 non-U-box panel · disease entity: SCAR16
    - span (full_text): “Third, all Ubox mutants had a reduced capacity to form polyubiquitin chains, perhaps due to altered interactions with E2 enzymes, whereas TPR and CC mutations were not defective in these same conditions ( Fig. 3 F ).”
    - extractor note: TPR and coiled-coil alleles show no chain-formation defect under these conditions, while all U-box alleles do.

- **o14** · PMID:42567515
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **substrate_selective**
    - system: recombinant protein biochemistry and cellular models, 13 variants
    - species: Homo sapiens · cell types: not stated
    - alleles: TPR-domain missense · disease entity: SCA48
    - span (abstract): “TPR variants retained intrinsic ligase activity but showed significantly reduced HSP70 binding, impaired substrate ubiquitination, and decreased stability.”
    - extractor note: Allelic dominant disorder (SCA48), not SCAR16: cross-entity, so it qualifies rather than settles the SCAR16 claim. Separates intrinsic catalysis from substrate ubiquitination.

- **o16** · PMID:35398354
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **unchanged**
    - system: biophysical, biochemical and cellular assays; C. elegans model
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Ala52Gly · disease entity: SCA48
    - span (abstract): “Utilizing an array of biophysical, biochemical, and cellular assays, we demonstrate that the CHIPA52G point mutant retains E3-ligase activity but has decreased affinity for chaperones.”
    - extractor note: Cross-entity (SCA48) and an allele outside the SCAR16 claim scope: a TPR-domain allele that is pathogenic while retaining ligase activity.

---

## Item 8 — `SCAR20:ac4-nonneural-clearance`

**Disease / gene:** SCAR20 / SNX14

**Upstream edge claim:** SNX14 Loss of Function contributes to Impaired Autophagosome Clearance in Neural Progenitors.

**Atomic claim to judge:** **SNX14 loss impairs autophagosome clearance in non-neural patient cells.**

**Scope**

- alleles: SNX14 knockout, biallelic SNX14 loss-of-function
- allele class: biallelic loss-of-function or knockout
- cell type scope: patient fibroblasts, HEK293
- disease scope: SCAR20
- readouts bearing on this claim: autolysosome_formation, autophagic_cargo_degradation, autophagosome_lysosome_fusion
- readouts counted as this capability at all: lc3_flux, lc3_ii_level, autophagosome_lysosome_fusion, autolysosome_formation, autophagic_cargo_degradation

**Evidence (1 item(s))**

- **s04** · PMID:29635513 (upstream wrote `url:https://pmc.ncbi.nlm.nih.gov/articles/PMC5961352/`)
    - citation: **UPSTREAM_ATTESTED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: autolysosome_formation · effect as extracted: **unchanged**
    - system: SCAR20 patient fibroblasts, marker colocalisation and p62 degradation
    - species: Homo sapiens · cell types: patient fibroblasts
    - alleles: biallelic SNX14 loss-of-function · disease entity: SCAR20
    - span (upstream_curated_snippet): “we observe a very strong colocalization of autophagosome and lysosome associated markers indicating the efficient formation of autolysosomes in SCAR20 mutant fibroblasts”
    - extractor note: Preserved autolysosome formation in patient fibroblasts under the tested conditions. Patient cells, but a non-neural cell type. Full text is not open access.

---

## Item 9 — `SCAR16:ac1-ubox-t246m`

**Disease / gene:** SCAR16 / STUB1

**Upstream edge claim:** Biallelic STUB1 Loss-of-Function Variants contributes to Loss of CHIP E3 Ubiquitin Ligase Activity.

**Atomic claim to judge:** **STUB1 p.Thr246Met causes loss of CHIP E3 ubiquitin ligase activity.**

**Scope**

- alleles: p.Thr246Met
- allele class: U-box missense: p.Thr246Met
- cell type scope: not scoped
- disease scope: SCAR16
- readouts bearing on this claim: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation
- readouts counted as this capability at all: e3_ligase_activity, hsc70_ubiquitination, hsp70_polyubiquitination, polyubiquitin_chain_formation

**Evidence (3 item(s))**

- **o01** · PMID:24113144
    - citation: **VERIFIED**, full text not retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **abolished**
    - system: recombinant protein and cell culture models
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Thr246Met · disease entity: SCAR16
    - span (abstract): “Introduction of the Thr246Met mutation into CHIP results in a loss of ubiquitin ligase activity measured directly using recombinant proteins as well as in cell culture models.”
    - extractor note: Family reported as Gordon Holmes syndrome; DisMech curates this presentation within SCAR16.

- **o05** · PMID:30222779
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: e3_ligase_activity · effect as extracted: **abolished**
    - system: biophysical and cellular assays; knock-in mouse and rat models in the same study
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Thr246Met · disease entity: SCAR16
    - span (abstract): “CHIP-T246M has no ligase activity, but maintains interactions with chaperones and chaperone-related functions.”

- **o06** · PMID:28396517
    - citation: **VERIFIED**, full text retrieved
    - origin: PRIMARY_RESULT
    - readout: hsc70_ubiquitination · effect as extracted: **abolished**
    - system: purified recombinant CHIP, in vitro ubiquitination, 37 C, 1 h
    - species: Homo sapiens · cell types: not stated
    - alleles: p.Thr246Met · disease entity: SCAR16
    - span (full_text): “Hsc70 seemed to be mono-ubiquitinated by the N65S mutant, while no Hsc70-ubiquitination was detected for T246M, confirming previous findings on these two variants [ 3 , 9 ].”

---
