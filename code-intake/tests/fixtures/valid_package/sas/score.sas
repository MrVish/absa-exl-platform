/* Synthetic SAS scoring code — valid fixture with balanced PROC/RUN. */
DATA scored;
  SET input;
  pd_score = 0.5 * income_band + 0.3 * tenure_months / 12 + 0.2 * delinquencies;
  IF pd_score > 0.7 THEN risk_band = 'HIGH';
  ELSE IF pd_score > 0.4 THEN risk_band = 'MEDIUM';
  ELSE risk_band = 'LOW';
RUN;

PROC PRINT data=scored;
RUN;
