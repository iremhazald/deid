# Open issues

These are recorded so they are not forgotten. They are not fixed here.
Each one needs its own code change.

## POLITICAL_INFORMATION is still in the schema

`POLITICAL_INFORMATION` is in `EntityType` and the tag catalog recommends
redacting it, but no scan produces it. It is out of scope. Needs a cleanup
decision, as a separate code change.

## A date of birth is not scored as a quasi-identifier

In `apps/api/app/privacy/reidentification.py`, `QUASI_IDENTIFIERS` contains
`DATE` with the comment "Date of birth", but not `DATE_OF_BIRTH`, while the
birth detectors emit `DATE_OF_BIRTH`. A detected but unmasked date of birth
is not counted in the risk score. Needs a separate code change with its own
test.
