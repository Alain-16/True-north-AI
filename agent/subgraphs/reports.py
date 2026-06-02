

def _display(obj:dict | None)->str | None:
    if not obj:
        return None
    return obj.get("display")

def _read_obs_value(obs:dict)-> tuple[object,str | None]:

    if obs.get("valueNumeric") is not None:
        return obs["valueNumeric"], "numeric"
    
    if obs.get("valueCoded") is not None:
        return _display(obs["valueCoded"]), "coded"
    
    if obs.get("valueBoolean") is not None:
        return obs["valueBoolean"], "boolean"
    
    if obs.get("valueDatetime") is not None:
        return obs["valueDatetime"], "datetime"
    
    if obs.get("valueText") is not None:
        return obs["valueText"], "text"
    return None, None


def shape_lab_result(obs:dict,concept:dict | None = None)-> dict:

    value, value_type = _read_obs_value(obs)
    concept_name = obs.get("concept") or {}

    reference_range = None
    units = None
    if concept:
        units = concept.get("units")
        bounds = {
              "low_normal":   concept.get("lowNormal"),
              "high_normal":  concept.get("hiNormal"),
              "low_critical": concept.get("lowCritical"),
              "high_critical": concept.get("hiCritical"),
        }

        if any(v is not None for v in bounds.values()):
            reference_range = bounds
    return {
          "obs_uuid":        obs.get("uuid"),
          "test":            _display(concept_name),
          "value":           value,
          "value_type":      value_type,
          "units":           units,
          "datetime":        obs.get("obsDatetime"),
          "concept_uuid":    concept_name.get("uuid"),
          "reference_range": reference_range,
          "comment":         obs.get("comment"),

    }

def shape_prescription(order: dict)-> dict:
    return {
          "order_uuid":          order.get("uuid"),
          "order_number":        order.get("orderNumber"),
          "drug":                _display(order.get("drug")) or _display(order.get("concept")),
          "dose":                order.get("dose"),            # raw number, kept as-is
          "dose_units":          _display(order.get("doseUnits")),
          "frequency":           _display(order.get("frequency")),
          "route":               _display(order.get("route")),
          "duration":            order.get("duration"),        # raw number, kept as-is
          "duration_units":      _display(order.get("durationUnits")),
          "status":              order.get("status"),          # ACTIVE | COMPLETED | ...
          "date_activated":      order.get("dateActivated"),
          "date_stopped":        order.get("dateStopped"),
          "auto_expire_date":    order.get("autoExpireDate"),
          "as_needed":           order.get("asNeeded"),
          "dosing_instructions": order.get("dosingInstructions"),
          "num_refills":         order.get("numRefills"),
          "orderer":             _display(order.get("orderer")),

    }