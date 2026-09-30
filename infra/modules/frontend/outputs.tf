output "bucket_name" { value = aws_s3_bucket.site.bucket }
output "distribution_id" {
  description = "CloudFront distribution ID (for invalidations)"
  value       = aws_cloudfront_distribution.site.id
}
output "distribution_domain_name" {
  description = "CloudFront domain name, e.g. d1234abcd.cloudfront.net."
  value       = aws_cloudfront_distribution.site.domain_name
}
