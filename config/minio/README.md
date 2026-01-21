# MinIO Configuration

MinIO configuration is handled via environment variables in docker-compose.yml.

## Post-Deployment Setup

After starting the cluster, access MinIO console at http://minio.localhost and:

1. **Create buckets:**
   - `echomind-documents` - Document storage
   - `echomind-avatars` - User avatars
   - `echomind-exports` - Data exports

2. **Set bucket policies** (if needed for public access):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {"AWS": ["*"]},
         "Action": ["s3:GetObject"],
         "Resource": ["arn:aws:s3:::echomind-documents/*"]
       }
     ]
   }
   ```

3. **Create access keys** for services (if needed)

## Production Recommendations

- Enable TLS
- Use strong access credentials
- Configure bucket lifecycle policies
- Enable versioning for critical buckets
- Set up replication for HA
