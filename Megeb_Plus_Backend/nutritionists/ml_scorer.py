import os, joblib
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ai_model.joblib")

FEATURE_ORDER = ["completeness", "format_valid", "dates_valid",
                 "consistency", "documents"]

def _features_from_result(ai_result):
    b = ai_result.get("breakdown", {})
    return [1 if b.get(k, {}).get("passed") else 0 for k in FEATURE_ORDER]

def train_from_queryset(applications):
    """applications: NutritionistApplication queryset with ai_result set
    and status in ('approved','rejected'). Trains + saves a RandomForest."""
    from sklearn.ensemble import RandomForestClassifier
    X, y = [], []
    for app in applications:
        if not app.ai_result or app.status not in ("approved", "rejected"):
            continue
        X.append(_features_from_result(app.ai_result))
        y.append(1 if app.status == "approved" else 0)
    if len(set(y)) < 2:
        raise ValueError("Need both approved and rejected examples to train.")
    clf = RandomForestClassifier(n_estimators=200, random_state=42)
    clf.fit(np.array(X), np.array(y))
    joblib.dump(clf, MODEL_PATH)
    return {"trained_on": len(y), "features": FEATURE_ORDER}

def ml_score(ai_result):
    """Return probability(0-100) that an application is genuine, or None."""
    if not os.path.exists(MODEL_PATH):
        return None
    clf = joblib.load(MODEL_PATH)
    proba = clf.predict_proba([_features_from_result(ai_result)])[0][1]
    return int(proba * 100)