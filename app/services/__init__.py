from app.services.auth import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    create_therapist_signup,
    create_user,
    generate_temp_password,
    hash_password,
    set_temporary_password,
    update_user,
    verify_password,
)
from app.services.therapist import (
    create_therapist,
    delete_therapist,
    get_therapist,
    get_therapist_by_user,
    get_therapist_dashboard,
    get_therapist_profile,
    get_therapists,
    update_therapist,
    update_therapist_profile,
)
from app.services.session import (
    create_session,
    delete_session,
    get_all_sessions,
    get_session,
    get_sessions_for_patient,
    get_sessions_for_therapist,
    reschedule_session,
    update_session,
)
from app.services.product import (
    create_product,
    delete_product,
    get_product,
    get_products,
    update_product,
)
from app.services.cart import (
    add_to_cart,
    clear_cart,
    get_cart,
    remove_cart_item,
    update_cart_item,
)
from app.services.payment import (
    create_payment,
    get_all_payments,
    get_payment,
    get_payments_for_user,
    update_payment,
)
from app.services.report import (
    create_report,
    delete_report,
    get_report,
    get_reports_for_patient,
    get_reports_for_therapist,
    update_report,
)
from app.services.patient import (
    generate_referral_code,
    get_my_patients,
    get_patient_dashboard,
    get_patient_profile,
    get_patient_referral,
    upsert_patient_profile,
)
from app.services.review import (
    create_review,
    get_completed_sessions_without_review,
    get_review_by_patient_and_therapist,
    get_review_by_session,
    get_reviews_for_patient,
)
from app.services.admin import (
    create_therapist_by_admin,
    delete_admin_patient,
    delete_admin_performance,
    delete_admin_therapist,
    get_admin_bookings,
    get_admin_dashboard_stats,
    get_admin_earnings,
    get_admin_patient,
    get_admin_patients,
    get_admin_performance,
    get_admin_performance_detail,
    get_admin_recent_activity,
    get_admin_therapist,
    get_admin_therapists,
    remove_from_team,
    resolve_therapist,
    schedule_review,
    update_admin_patient,
    update_admin_performance,
    update_admin_therapist,
)
from app.services.availability import (
    apply_recurring_pattern,
    apply_schedule,
    approve_block_request,
    block_date,
    block_range,
    bulk_update_slots,
    create_audit_entry,
    create_block_request,
    delete_audit_entry,
    delete_recurring_pattern,
    generate_availability,
    get_audit_entries,
    get_monthly_availability,
    get_pending_block_requests,
    get_recurring_patterns,
    get_slots_for_range,
    get_therapist_block_requests,
    get_working_days,
    get_working_hours,
    open_full_month,
    reject_block_request,
    set_slot_status,
    toggle_recurring_pattern,
    unblock_item,
    update_working_hours,
)
from app.services.complaint import (
    assign_complaint,
    create_complaint,
    delete_complaint,
    get_complaint,
    get_complaints,
    update_complaint,
)
from app.services.service_area import (
    assign_therapist_to_area,
    create_service_area,
    delete_service_area,
    get_service_area,
    get_service_areas,
    update_service_area,
)
from app.services.refund import (
    assign_refund,
    create_manual_case,
    create_refund,
    delete_refund,
    get_refund,
    get_refund_stats,
    get_refunds,
    update_refund,
)
from app.services.activity_log import log_admin_activity, get_activity_logs
from app.services.service import (
    create_service,
    delete_service,
    get_service,
    get_services,
    update_service,
)
from app.services.clinic import (
    create_clinic,
    delete_clinic,
    get_clinic,
    get_clinics,
    update_clinic,
)
from app.services.package import (
    create_package,
    delete_package,
    get_package,
    get_packages,
    update_package,
)
from app.services.google_auth import verify_google_credential, find_or_create_google_user
from app.services.onboarding import (
    complete_onboarding,
    get_onboarding_status,
    save_onboarding_progress,
)
from app.services.therapist_application import (
    get_application_sections,
    get_application_status,
    update_therapist_application,
)
