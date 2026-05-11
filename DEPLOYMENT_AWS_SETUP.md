# AWS Elastic Beanstalk Setup Guide — EduFlow

This guide walks through deploying EduFlow to AWS Elastic Beanstalk.

---

## Prerequisites

```bash
# Install AWS CLI
brew install awscli

# Install EB CLI
brew install aws-elasticbeanstalk

# Configure AWS credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (e.g., us-east-1), Output format (json)

# Verify
aws sts get-caller-identity
```

---

## Step 1: Create S3 Bucket for File Uploads

```bash
# Create bucket (replace with your domain/project name)
aws s3api create-bucket \
  --bucket eduflow-uploads-prod \
  --region us-east-1

# Block public access
aws s3api put-public-access-block \
  --bucket eduflow-uploads-prod \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable versioning for safety
aws s3api put-bucket-versioning \
  --bucket eduflow-uploads-prod \
  --versioning-configuration Status=Enabled

# Enable lifecycle to delete old versions after 30 days
cat > /tmp/lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "Id": "DeleteOldVersions",
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 30
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket eduflow-uploads-prod \
  --lifecycle-configuration file:///tmp/lifecycle.json
```

---

## Step 2: Create IAM Role for EB Instance

```bash
# Create trust policy
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name eduflow-eb-role \
  --assume-role-policy-document file:///tmp/trust-policy.json

# Create S3 access policy
cat > /tmp/s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::eduflow-uploads-prod/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::eduflow-uploads-prod"
    }
  ]
}
EOF

# Attach policy
aws iam put-role-policy \
  --role-name eduflow-eb-role \
  --policy-name eduflow-s3-access \
  --policy-document file:///tmp/s3-policy.json

# Attach standard EB policy
aws iam attach-role-policy \
  --role-name eduflow-eb-role \
  --policy-arn arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name eduflow-eb-instance-profile

aws iam add-role-to-instance-profile \
  --instance-profile-name eduflow-eb-instance-profile \
  --role-name eduflow-eb-role
```

---

## Step 3: Initialize Elastic Beanstalk Application

```bash
# Navigate to project root
cd /path/to/EduFlow-Edu_v2-2

# Initialize EB (creates .elasticbeanstalk/config.yml)
eb init -p python-3.11 eduflow-backend --region us-east-1

# Create environment
eb create eduflow-prod \
  --instance-type t3.small \
  --scale 1

# Wait for environment to be healthy (2-5 minutes)
eb status
```

---

## Step 4: Configure Environment Variables

Create a file `.env.production` with your secrets:

```bash
MONGO_URL=mongodb+srv://user:password@cluster.mongodb.net/eduflow
DB_NAME=eduflow
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
ENVIRONMENT=production
JWT_SECRET=<generate-strong-64-char-random-string>
AZURE_OPENAI_API_KEY=<your-azure-key>
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.3-chat
GEMINI_API_KEY=<your-gemini-key>
AWS_ACCESS_KEY_ID=<your-aws-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret>
AWS_REGION=ap-south-1
S3_BUCKET_NAME=eduflow-uploads-prod
```

Set environment variables in EB:

```bash
# Using EB CLI
eb setenv \
  MONGO_URL="mongodb+srv://..." \
  DB_NAME="eduflow" \
  JWT_SECRET="your-secret-here" \
  CORS_ORIGINS="https://yourdomain.com" \
  ENVIRONMENT="production" \
  AZURE_OPENAI_API_KEY="..." \
  AZURE_OPENAI_ENDPOINT="..." \
  AZURE_OPENAI_DEPLOYMENT="gpt-5.3-chat" \
  GEMINI_API_KEY="..." \
  AWS_REGION="ap-south-1" \
  S3_BUCKET_NAME="eduflow-uploads-prod"

# Verify
eb printenv
```

---

## Step 5: Deploy Backend

```bash
# Test locally first
cd backend
pip install -r requirements.txt
gunicorn server:app --bind 0.0.0.0:8000

# If that works, deploy to EB
eb deploy

# Check logs
eb logs

# Open in browser
eb open
```

---

## Step 6: Setup Frontend (Separate EB Environment or S3+CloudFront)

### Option A: Separate EB Environment for Frontend (Easy)

```bash
# Create React production build locally
cd frontend
npm run build
# Creates frontend/build/ directory

# Create separate EB app for frontend
eb init -p node.js-18 eduflow-frontend --region us-east-1
eb create eduflow-frontend-prod

# Deploy (creates Procfile for Node/Express server)
eb deploy
```

### Option B: S3 + CloudFront (Better for Static Files)

```bash
# Build React app
cd frontend
npm run build

# Create S3 bucket for frontend
aws s3api create-bucket \
  --bucket eduflow-frontend-prod \
  --region us-east-1

# Enable static website hosting
aws s3api put-bucket-website \
  --bucket eduflow-frontend-prod \
  --website-configuration '{
    "IndexDocument": {"Suffix": "index.html"},
    "ErrorDocument": {"Key": "index.html"}
  }'

# Upload build directory
aws s3 sync frontend/build/ s3://eduflow-frontend-prod/ --delete

# Create CloudFront distribution
aws cloudfront create-distribution \
  --distribution-config '{
    "DefaultRootObject": "index.html",
    "Origins": {
      "Items": [
        {
          "Id": "myOrigin",
          "DomainName": "eduflow-frontend-prod.s3.amazonaws.com",
          "S3OriginConfig": {}
        }
      ]
    },
    "DefaultCacheBehavior": {
      "TargetOriginId": "myOrigin",
      "ViewerProtocolPolicy": "redirect-to-https",
      "TrustedSigners": {
        "Enabled": false
      },
      "ForwardedValues": {
        "QueryString": false,
        "Cookies": {"Forward": "none"}
      },
      "MinTTL": 0
    },
    "Enabled": true
  }'
```

---

## Step 7: Setup Domain & SSL

```bash
# Use Route53 to point domain to EB/CloudFront
# OR use EB's built-in domain (eduflow-prod.elasticbeanstalk.com)

# Request SSL certificate (free via ACM)
aws acm request-certificate \
  --domain-name yourdomain.com \
  --subject-alternative-names "*.yourdomain.com" \
  --domain-validation-options "*.yourdomain.com" \
  --region us-east-1

# Configure EB listener with HTTPS
# (via EB console: Environment > Load Balancer > HTTPS)
```

---

## Step 8: Update Frontend API URL

Create `frontend/.env.production`:

```bash
REACT_APP_BACKEND_URL=https://api.yourdomain.com
REACT_APP_ENVIRONMENT=production
```

Deploy frontend build with this new URL:

```bash
cd frontend
npm run build
aws s3 sync build/ s3://eduflow-frontend-prod/ --delete
```

---

## Monitoring & Logs

```bash
# View EB logs
eb logs

# SSH into instance (if needed)
eb ssh

# View CloudWatch logs
aws logs tail /aws/elasticbeanstalk/eduflow-prod/var/log/eb-engine.log --follow

# Monitor application
eb status
eb health
```

---

## Rollback

```bash
# If deployment fails
eb abort

# Or revert to previous version
eb appversion list
eb setenv AWS_ELASTICBEANSTALK_VERSION=<previous-version>
```

---

## Cleanup (Delete When Done)

```bash
# Delete EB environment
eb terminate eduflow-prod

# Delete S3 buckets
aws s3 rb s3://eduflow-uploads-prod --force
aws s3 rb s3://eduflow-frontend-prod --force

# Delete IAM role
aws iam delete-instance-profile --instance-profile-name eduflow-eb-instance-profile
aws iam delete-role --role-name eduflow-eb-role
aws iam delete-role-policy --role-name eduflow-eb-role --policy-name eduflow-s3-access
```

---

## Troubleshooting

### EB Instance Won't Start

```bash
# Check logs
eb logs

# Common issues:
# - MONGO_URL not set → set via eb setenv
# - JWT_SECRET missing → set via eb setenv
# - Database unreachable → check MongoDB Atlas network rules
```

### Uploads Not Working

```bash
# Check S3 bucket
aws s3 ls s3://eduflow-uploads-prod/

# Check IAM role has S3 access
aws iam get-role-policy \
  --role-name eduflow-eb-role \
  --policy-name eduflow-s3-access
```

### CORS Errors

```bash
# Update CORS_ORIGINS env var
eb setenv CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"

# Restart
eb restart
```

---

## Performance Optimization

```bash
# Enable auto-scaling
eb scale 2  # Start with 2 instances

# Configure scaling policies
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name <asg-name> \
  --policy-name scale-up \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration TargetValue=70,PredefinedMetricSpecification='{PredefinedMetricType=ASGAverageCPUUtilization}'

# Enable gzip compression
# (Add to .ebextensions/01_environment.config)
```

---

## Cost Estimation

| Service | Instance | Monthly Cost |
|---------|----------|--------------|
| EB (t3.small) | 1 instance | $30 |
| Data transfer | ~100GB | $10 |
| S3 (uploads) | 1000 files × 5MB | $5 |
| CloudFront | 100GB/month | $8 |
| **Total** | | **~$53/month** |

Actual costs will vary based on traffic and storage.

---

## Next Steps

1. **Before deploying:** Update all environment variables in EB console
2. **After deploying:** Test login, upload files, run smoke tests
3. **Monitor:** Set up CloudWatch alarms for errors and high CPU
4. **Backup:** Configure MongoDB Atlas automated backups
5. **CI/CD:** Set up GitHub Actions to auto-deploy on push
