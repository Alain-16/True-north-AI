import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from pgvector.sqlalchemy import Vector
from core.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id = sa.Column(sa.Uuid,primary_key=True,server_default=sa.text("gen_random_uuid()"))
    openmrs_patient_id  = sa.Column(sa.String(50), unique=True, nullable=False)
    whatsapp_phone      = sa.Column(sa.String(20), unique=True)
    web_email           = sa.Column(sa.String(255), unique=True)
    status              = sa.Column(sa.String(30), nullable=False, server_default=sa.text("'pending_channel_link'"))
    preferred_channel   = sa.Column(sa.String(10), server_default=sa.text("'whatsapp'"))
    language            = sa.Column(sa.String(10), server_default=sa.text("'en'"))
    preferred_doctor_id = sa.Column(sa.String(50))
    reminder_lead_days  = sa.Column(ARRAY(sa.Integer), server_default=sa.text("'{7,1}'::integer[]"))
    reminder_lead_hours = sa.Column(ARRAY(sa.Integer), server_default=sa.text("'{2}'::integer[]"))
    created_at          = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    updated_at          = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))


class OTPToken(Base):
    __tablename__ = "otp_tokens"

    id         = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))
    phone      = sa.Column(sa.String(20), nullable=False)
    token      = sa.Column(sa.String(6), nullable=False)
    purpose    = sa.Column(sa.String(30), nullable=False)  
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    used       = sa.Column(sa.Boolean, server_default=sa.text("FALSE"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
         
          sa.Index("idx_otp_phone_purpose", "phone", "purpose",
                   postgresql_where=sa.text("NOT used")),
      )


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id             = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))
    patient_id     = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"), nullable=False)
    channel        = sa.Column(sa.String(10), nullable=False)  
    thread_id      = sa.Column(sa.String(100), unique=True, nullable=False)  
    current_flow   = sa.Column(sa.String(30))  
    started_at     = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    last_active_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    ended_at       = sa.Column(sa.DateTime(timezone=True))

    __table_args__ = (
          sa.Index("idx_sessions_patient_channel", "patient_id", "channel"),
      )


class AppointmentRecord(Base):
    __tablename__ = "appointment_records"

    id              = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))
    patient_id      = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"), nullable=False)
    openmrs_appt_id = sa.Column(sa.String(50), unique=True, nullable=False)
    source          = sa.Column(sa.String(20), nullable=False, server_default=sa.text("'agent'"))
    doctor_name     = sa.Column(sa.String(100))
    specialty       = sa.Column(sa.String(100))
    scheduled_at    = sa.Column(sa.DateTime(timezone=True), nullable=False)
    status          = sa.Column(sa.String(20), server_default=sa.text("'scheduled'"))
    created_at      = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    updated_at      = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
          sa.Index("idx_appts_patient", "patient_id"),
          sa.Index("idx_appts_scheduled", "scheduled_at"),
      )


class ReminderSchedule(Base):
    __tablename__ = "reminder_schedules"

    id              = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))
    patient_id      = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"), nullable=False)
    appointment_id  = sa.Column(sa.Uuid, sa.ForeignKey("appointment_records.id"))
    event_type      = sa.Column(sa.String(30), nullable=False)  
    trigger_at      = sa.Column(sa.DateTime(timezone=True), nullable=False)
    channel         = sa.Column(sa.String(10), nullable=False)
    template_name   = sa.Column(sa.String(50))
    status          = sa.Column(sa.String(20), server_default=sa.text("'pending'"))
    sent_at         = sa.Column(sa.DateTime(timezone=True))
    delivery_status = sa.Column(sa.String(20))
    message_id      = sa.Column(sa.String(100))  
    created_at      = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
          
          sa.Index("idx_reminders_trigger", "trigger_at",
                   postgresql_where=sa.text("status = 'pending'")),
          sa.Index("idx_reminders_patient", "patient_id"),
      )


class ReportDeliveryLog(Base):
    __tablename__ = "report_delivery_log"

    id                      = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))
    patient_id              = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"), nullable=False)
    openmrs_resource_id     = sa.Column(sa.String(100), nullable=False)  
    resource_type           = sa.Column(sa.String(30), nullable=False)   
    channel                 = sa.Column(sa.String(10), nullable=False)
    delivery_status         = sa.Column(sa.String(20), server_default=sa.text("'pending'"))
    ai_explanation_summary  = sa.Column(sa.Text)
    delivered_at            = sa.Column(sa.DateTime(timezone=True))
    patient_acknowledged_at = sa.Column(sa.DateTime(timezone=True))
    created_at              = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
          
          sa.UniqueConstraint("patient_id", "openmrs_resource_id", name="uq_report_patient_resource"),
      )


class MedicalKnowledge(Base):
    __tablename__ = "medical_knowledge"

    id         = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))
    embedding  = sa.Column(Vector(1536))           
    content    = sa.Column(sa.Text, nullable=False)
    category   = sa.Column(sa.String(30), nullable=False)   
    source     = sa.Column(sa.String(100), nullable=False)  
    source_id  = sa.Column(sa.String(100))
    version    = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
          
          sa.Index("idx_knowledge_category", "category"),
      )


class MedicalProfile(Base):
    __tablename__ = "medical_profiles"

    id = sa.Column(sa.Uuid, primary_key=True,server_default=sa.text("gen_random_uuid()"))
    patient_id = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"),unique=True,nullable=False)
    profile = sa.Column(JSONB,nullable=False,server_default=sa.text("'{}'::jsonb"))
    last_source = sa.Column(sa.String(100))
    version = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    created_at = sa.Column(sa.DateTime(timezone=True),nullable=False,server_default=sa.text("NOW()"))
    updated_at = sa.Column(sa.DateTime(timezone=True),nullable=False,server_default=sa.text("NOW()"))



class RefreshToken(Base):                                   
    __tablename__ = "refresh_tokens"

    id          = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))   
    patient_id  = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"), nullable=False)                    
    expires_at  = sa.Column(sa.DateTime(timezone=True), nullable=False)                                
    revoked     = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("FALSE"))               

    replaced_by_id = sa.Column(sa.Uuid, sa.ForeignKey("refresh_tokens.id"))                            
    created_at  = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))  
    last_used_at = sa.Column(sa.DateTime(timezone=True))                                               

    __table_args__ = (
        sa.Index("idx_refresh_patient", "patient_id"),                                                
    )