import pandas as pd

class OnLevelPremiumCalculator:
    def __init__(self, premiums_df, rate_changes_df):
        """
        premiums_df columns:
            accident_year
            earned_premium

        rate_changes_df columns:
            effective_date
            rate_change

        Example rate_change:
            0.05  = +5%
           -0.02 = -2%
        """
        self.premiums = premiums_df.copy()
        self.rate_changes = rate_changes_df.copy()

    # --------------------------------------------------
    # BUILD RATE LEVELS
    # --------------------------------------------------
    def build_rate_levels(self):
        self.rate_changes["effective_date"] = pd.to_datetime(self.rate_changes["effective_date"])
        rate_changes = self.rate_changes.sort_values("effective_date")
        
        steps = [(1900.0, 1.0)]
        current_level = 1.0
        
        def to_float_year(dt):
            year = dt.year
            start_of_year = pd.Timestamp(f"{year}-01-01")
            end_of_year = pd.Timestamp(f"{year+1}-01-01")
            days_in_year = (end_of_year - start_of_year).days
            day_of_year = (dt - start_of_year).days
            return year + day_of_year / days_in_year
            
        for _, row in rate_changes.iterrows():
            f_yr = to_float_year(row["effective_date"])
            current_level *= (1.0 + row["rate_change"])
            steps.append((f_yr, current_level))
            
        self.rate_steps = steps
        self.current_rate_level = current_level

    # --------------------------------------------------
    # AVERAGE RATE LEVEL FOR AN AY (PARALLELOGRAM METHOD)
    # --------------------------------------------------
    def average_rate_level(self, ay):
        Y = float(ay)
        
        # Integrate L(w) over [Y-1, Y+1]
        boundaries = [Y-1, Y, Y+1]
        for f_yr, _ in self.rate_steps:
            if Y-1 < f_yr < Y+1:
                boundaries.append(f_yr)
        boundaries = sorted(list(set(boundaries)))
        
        weighted_rl = 0.0
        for i in range(len(boundaries) - 1):
            a = boundaries[i]
            b = boundaries[i+1]
            
            # Find rate level in effect at a
            l = 1.0
            for f_yr, level in self.rate_steps:
                if f_yr <= a:
                    l = level
                    
            # Integrate based on which half of [Y-1, Y+1] the segment belongs to
            if a >= Y-1 and b <= Y:
                # First half: written in year Y-1, earned in year Y
                contrib = l * ((b + 1 - Y)**2 - (a + 1 - Y)**2) / 2.0
            else:
                # Second half: written in year Y, earned in year Y
                contrib = l * ((Y + 1 - a)**2 - (Y + 1 - b)**2) / 2.0
                
            weighted_rl += contrib
            
        return weighted_rl

    # --------------------------------------------------
    # CALCULATE ON-LEVEL PREMIUMS
    # --------------------------------------------------
    def calculate(self):
        if self.rate_changes.empty:
            # If no rate changes, just return premiums with olf=1.0
            results = []
            for _, row in self.premiums.iterrows():
                ay = row["accident_year"]
                earned_premium = row["earned_premium"]
                results.append({
                    "accident_year": ay,
                    "earned_premium": earned_premium,
                    "average_rate_level": 1.0,
                    "olf": 1.0,
                    "on_level_premium": earned_premium
                })
            return pd.DataFrame(results)

        self.build_rate_levels()

        results = []
        for _, row in self.premiums.iterrows():
            ay = row["accident_year"]
            earned_premium = row["earned_premium"]

            avg_rl = self.average_rate_level(ay)

            olf = (
                self.current_rate_level / avg_rl
            ) if avg_rl > 0 else 1.0

            on_level_premium = (
                earned_premium * olf
            )

            results.append({
                "accident_year": ay,
                "earned_premium": earned_premium,
                "average_rate_level": round(avg_rl, 4),
                "olf": round(olf, 4),
                "on_level_premium": round(on_level_premium, 2)
            })

        return pd.DataFrame(results)
