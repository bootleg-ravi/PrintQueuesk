from config.firebase_config import db

def update_job_status(job_id, status, details=None):
    """
    Updates the status of a job in Firebase.
    Args:
        job_id (int or str): The ID of the job to update.
        status (str): The new status for the job.
        details (str, optional): Additional details to log.
    Returns:
        bool: True if the update was successful, False otherwise.
    """
    try:
        job_ref = db.reference(f'jobs/print_jobs/{str(job_id)}')
        update_data = {'status': status}
        if details:
            update_data['details'] = str(details)
        job_ref.update(update_data)
        return True
    except Exception as err:
        print(f"Error updating job status in Firebase: {err}")
        return False
