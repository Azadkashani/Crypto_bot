# FILE: src/strategy/signal/signal_quality_engine.py

def _score_zone(self, zone: FTRZone) -> tuple:
    """امتیازدهی به کیفیت Zone"""
    score = 0.0
    positive = []
    warnings = []
    
    if zone.zone_midpoint > 0:
        height_pct = zone.zone_height / zone.zone_midpoint
        
        if height_pct <= 0.02:
            score += self.config.zone_weight * 0.4
            positive.append(f"Tight zone: {height_pct:.4f}")
        elif height_pct <= 0.05:
            score += self.config.zone_weight * 0.2  # ← اصلاح: امتیاز متوسط
            positive.append(f"Moderate zone: {height_pct:.4f}")
        else:
            warnings.append(f"Wide zone: {height_pct:.4f}")
            score += self.config.zone_weight * 0.1  # ← اصلاح: حداقل امتیاز
    
    if zone.state == FTRZoneState.FIRST_TOUCH:
        score += self.config.zone_weight * 0.3
        positive.append("Zone in first touch state")
    elif zone.state == FTRZoneState.ACTIVE:
        score += self.config.zone_weight * 0.2
        positive.append("Zone active")
    
    if zone.invalidation_level is not None:
        if zone.direction == "LONG":
            if zone.invalidation_level < zone.zone_low:
                score += self.config.zone_weight * 0.3
                positive.append("Valid invalidation level")
        else:
            if zone.invalidation_level > zone.zone_high:
                score += self.config.zone_weight * 0.3
                positive.append("Valid invalidation level")
    
    return min(score, self.config.zone_weight), positive, warnings
