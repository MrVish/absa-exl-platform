/* Synthetic broken fixture — PROC FREQ has no matching RUN. */
DATA scored;
  SET input;
  pd_score = 0.5;
RUN;

PROC FREQ data=scored;
  TABLES risk_band;
/* missing RUN; */
