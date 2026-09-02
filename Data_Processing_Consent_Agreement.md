# DATA PROCESSING & PRIVACY CONSENT AGREEMENT

**The Aaryans School, Joya, Amroha**
Powered by EduFlow — operated by Layaa AI Pvt. Ltd.

**Version 1.0 | Effective: September 2026**

---

## PARTIES TO THIS AGREEMENT

This agreement is between **The Aaryans School, Joya, Amroha, Uttar Pradesh** ("the School") and the parent or guardian signing below ("the Parent"), on behalf of their child enrolled at the School.

---

## 1. WHY WE ARE ASKING FOR YOUR CONSENT

The School uses a digital platform called **EduFlow** to manage student records, attendance, fees, and communication. Running this platform requires sharing certain data with trusted technology providers. Under India's **Digital Personal Data Protection Act, 2023 (DPDP Act)**, we are required to inform you clearly about what data is collected, how it is used, and with whom it is shared — and to obtain your written consent.

---

## 2. WHAT DATA WE COLLECT

**About your child:**
- Full name, date of birth, photograph, and admission number
- Class, section, house, roll number
- Attendance records and academic marks
- Fee payment history and outstanding dues
- Transport route and bus details (if applicable)
- Health and medical notes (if recorded by school)
- Documents uploaded by school staff (certificates, ID cards)

**About you (the parent / guardian):**
- Name, phone number, and home address
- Your relationship to the child
- Communication and notification preferences

**What we do NOT collect:**
- Passwords — stored as one-way encrypted values that no one, including our team, can reverse
- Payment card or bank account numbers — payments go through a licensed gateway; card details never reach our servers

---

## 3. HOW YOUR DATA IS USED

| Purpose | Who carries it out |
|---|---|
| Maintaining student academic and attendance records | School staff, within EduFlow |
| Sending fee reminders and school notices by SMS | Twilio Inc. (USA) |
| AI assistant for school staff to answer queries about records | Microsoft Azure OpenAI (USA) |
| Catching and reporting platform errors | Sentry (USA) |
| Understanding how the platform is used so it can be improved | PostHog Inc. (USA) |
| Understanding how staff navigate the platform | Microsoft Clarity (USA / EU) |
| Storing photographs, certificates, and uploaded documents | Amazon Web Services S3 — Mumbai, India |
| Platform health and usage telemetry | LayaaStat, operated by Layaa AI Pvt. Ltd. |

---

## 4. THIRD-PARTY SERVICES — WHAT THEY RECEIVE AND WHY

### Amazon-Nova-2 from Amazon Web Services
School staff use an AI assistant called "Flo" to answer questions about attendance, fees, and student records. When a staff member asks a question, relevant school data is sent to Amazon's servers to generate the response. Amazon processes this data under enterprise data protection terms and **does not use school data to train its public AI models**. No student or parent data is sent to Amazon servers unless a staff member explicitly asks about a specific child during their session.

### Sentry
When a technical error occurs on the platform, Sentry captures a report so our development team can identify and fix the problem. **All form inputs and typed text are masked before the report leaves the browser** — passwords, names, and phone numbers are replaced with dots and are never visible in error reports. Sentry is used solely for platform reliability, not for advertising or profiling.

### PostHog
PostHog collects anonymous usage data — which screens are visited and which buttons are clicked — to help us understand how to improve the platform. It does not collect names, phone numbers, or any information that could identify a specific person.

### Microsoft Clarity
Clarity records how staff members navigate the platform — where they scroll and what they click. **All form fields and screen text are masked** before any recording is created. Clarity data is used only to improve the platform's design and is never used for advertising.

### Twilio Inc.
When the school sends an SMS fee reminder or notification, your phone number is passed to Twilio to deliver the message. Twilio does not retain your number for marketing or any other purpose.

### Amazon Web Services (AWS) — S3, Mumbai
All student photographs, certificates, and uploaded documents are stored on AWS servers located in **Mumbai, India**. Files are accessible only through time-limited signed links issued to authorised school staff. Documents do not leave India.

### LayaaStat
Anonymous platform health metrics (server uptime, error rates, AI response times) are sent to LayaaStat, operated by Layaa AI Pvt. Ltd. No student or parent personal data is included in these metrics.

---

## 5. DATA STORED OUTSIDE INDIA

The following services process data on servers outside India, primarily in the United States:

| Service | Data sent | Purpose |
|---|---|---|
| Microsoft Azure OpenAI | Relevant school records during a staff query | AI assistant responses |
| Sentry | Masked error snapshots (no personal data) | Platform error tracking |
| PostHog | Anonymous page view and click events | Usage analytics |
| Microsoft Clarity | Masked navigation recordings | UX improvement |
| Twilio | Your phone number (to deliver the SMS) | SMS delivery |

Student photographs and all uploaded documents are stored in India (AWS Mumbai) and do not leave India.

All overseas providers are bound by data processing agreements requiring them to handle data responsibly and to use it only for the specific purpose stated above.

---

## 6. DATA RETENTION

| Data | Kept for |
|---|---|
| Student academic and attendance records | Duration of enrolment + 5 years |
| Fee transaction records | 7 years (statutory requirement) |
| Staff records | Duration of employment + 2 years |
| Platform error logs (Sentry) | 90 days |
| Analytics data (PostHog, Clarity) | As per each provider's standard terms |
| Uploaded files (photographs, certificates) | Duration of enrolment, or until deleted by authorised staff |

---

## 7. HOW WE PROTECT YOUR DATA

- All data is transferred over **HTTPS** (encrypted in transit)
- Passwords are protected using **bcrypt** — a one-way hash that cannot be reversed
- Each school's data is kept completely separate — no school can access another school's records
- Access requires a personal login; each staff member sees only what their role permits
- Sessions automatically close after **one hour of inactivity**
- Student photographs and documents are stored in the school's own private storage bucket, inaccessible without a time-limited authorisation

---

## 8. YOUR RIGHTS UNDER THE DPDP ACT 2023

India's Digital Personal Data Protection Act 2023 gives you the right to:

- **Know** what personal data the School holds about you and your child
- **Access** a copy of that data on request
- **Correct** any data that is inaccurate or out of date
- **Request erasure** of data that is no longer needed for the purpose it was collected
- **Withdraw consent** at any time for processing that is not strictly required to provide the school service
- **Raise a grievance** with the School's designated data officer if you believe your data has been handled incorrectly

To exercise any of these rights, submit a written request to the School office. The School will respond within **30 days**.

---

## 9. CHANGES TO THIS AGREEMENT

If this agreement changes in a way that materially affects how your data is used, the School will notify you before the change takes effect. Continued use of platform services after that notification constitutes acceptance of the updated terms.

---

## 10. CONTACT

**For data privacy questions or requests:**

The Aaryans School
Joya, Amroha, Uttar Pradesh — 244241
Phone: ________________________
Email: ________________________

**For platform-related data requests:**
Layaa AI Pvt. Ltd.
Email: support@layaa.ai

---

## CONSENT DECLARATION

I confirm that I have read and understood this Data Processing & Privacy Consent Agreement. I give my consent for The Aaryans School to collect and process my personal data and my child's personal data as described above, for the purpose of managing school operations through the EduFlow platform.

I understand that I may withdraw this consent at any time by writing to the School office, and that withdrawal of consent may affect the School's ability to provide certain digital services.

&nbsp;

| | |
|---|---|
| **Parent / Guardian full name:** | __________________________________ |
| **Relationship to student:** | __________________________________ |
| **Student full name:** | __________________________________ |
| **Class & Section:** | __________________________________ |
| **Admission Number:** | __________________________________ |
| **Signature:** | __________________________________ |
| **Date:** | __________________________________ |

&nbsp;

*For office use only*

| | |
|---|---|
| **Received by:** | __________________________________ |
| **Date received:** | __________________________________ |
| **Filed in student record:** | ☐ Yes |

---

*This agreement is issued by The Aaryans School in compliance with the Information Technology Act 2000, the Digital Personal Data Protection Act 2023, and applicable guidelines issued by the Data Protection Board of India.*
