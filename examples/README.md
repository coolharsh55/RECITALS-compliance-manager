# Example data

One compliant and one non-compliant data set for each supported article, all
about the employee data of a fictional company, Harbourview Software Ltd: its
employee records and payroll (GDPR), its cloud HR and payroll platform as an
essential entity (NIS2), and its high-risk CV-screening model TalentMatch
(AI Act).

Each non-compliant file is its compliant file with one change, marked
`NON-COMPLIANT CHANGE` in the data, so it gives exactly one finding:

| Article | Files | Change in the non-compliant file | Finding |
|---|---|---|---|
| GDPR Art. 30 | `gdpr30_*.ttl` | employee records activity has no storage duration | `A30-1-24` |
| GDPR Art. 32 | `gdpr32_*.ttl` | HR system no longer encrypts records that include health data | `A32-1-a` |
| NIS2 Art. 20 | `nis2_20_*.ttl` | board members take no cybersecurity training | `N20-2-1` |
| NIS2 Art. 21 | `nis2_21_*.ttl` | no incident handling procedure | `N21-2-b` |
| EU AI Act Art. 10 | `eu_ai_act_10_*.ttl` | training data not examined for biases | `AIA10-2-f` |
| EU AI Act Art. 11 | `eu_ai_act_11_*.ttl` | documentation covers 2.0.0, version 2.1.0 is on the market | `AIA11-1-3` |

The files use DPV 2.3 terms wherever DPV has one: HR purposes
(`dpv:PersonnelPayment`, `dpv:RecruitmentManagement`), `dpv:Employee`,
`pd:` personal data categories (`pd:Salary`, `pd:HealthRecord`), and DPV
measures. The AI Act files use DPV's AI Act extension (`eu-aiact:HighRiskAISystem`,
`eu-aiact:TrainingData`, `eu-aiact:TechnicalDocumentation` and its Annex IV
parts) and the `ai:` and `tech:` extensions (`ai:hasTrainingData`,
`ai:BiasAssessment`, `tech:hasProvider`). Instances carry both the general DPV
class the shapes check (`dpv:Purpose`, `eu-aiact:HighRiskAISystem`) and the
specific concept, since the DPV ontology is not loaded during the check.
`recitals:` terms appear only where a check needs them and DPV has none: the
NIS2 management body, approval and oversight, and four AI Act Art. 10 data
governance practices (design choices, assumptions, data gaps, statistical
properties). The Art. 11 files use no `recitals:` terms.

The GDPR Art. 30 files list a representative and joint controllers, since the
current shapes require them for every record.

`previous/` keeps the earlier examples: the GDPR Art. 30 sample
(`gdpr30_example.ttl`) and the earlier non-compliant files, each with many
gaps. The tests use them to cover most failing checks.

## Running one

Start the stack and follow the three steps in the main
[README](../README.md#usage): create a use case for the law, upload the file,
run the check. Use a separate use case for each file (any ID, for example
`gdpr32-compliant`), or clear the use case between files, since all uploads
to a use case are validated together.

`tests/test_examples.py` checks that every file still gives the results its
header describes.
