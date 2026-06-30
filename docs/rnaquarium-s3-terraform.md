# RNAquarium S3 Terraform Proposal

This repository does not own the Terraform stack, so this file is a draft
blueprint for the infra PR that should create or wire the shared RNAquarium S3
bucket for Gene2Fish.

## Desired S3 Layout

```text
s3://czbsf-rnaquarium/gene2fish/data/image_metadata_v2.json
s3://czbsf-rnaquarium/gene2fish/data/gene_aliases.json
s3://czbsf-rnaquarium/gene2fish/zfin-images/imageLoadUp/...
```

## Example Terraform

If `czbsf-rnaquarium` already exists, replace the bucket resource with a data
source and keep the IAM/policy wiring.

```hcl
locals {
  rnaquarium_bucket_name = "czbsf-rnaquarium"
  gene2fish_prefix      = "gene2fish"
}

resource "aws_s3_bucket" "rnaquarium" {
  bucket = local.rnaquarium_bucket_name
}

resource "aws_s3_bucket_public_access_block" "rnaquarium" {
  bucket = aws_s3_bucket.rnaquarium.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "rnaquarium" {
  bucket = aws_s3_bucket.rnaquarium.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "rnaquarium" {
  bucket = aws_s3_bucket.rnaquarium.id

  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "gene2fish_rnaquarium_read" {
  statement {
    sid = "ReadGene2FishObjects"

    actions = [
      "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.rnaquarium.arn}/${local.gene2fish_prefix}/data/*",
      "${aws_s3_bucket.rnaquarium.arn}/${local.gene2fish_prefix}/zfin-images/*",
    ]
  }
}

resource "aws_iam_policy" "gene2fish_rnaquarium_read" {
  name   = "gene2fish-rnaquarium-read"
  policy = data.aws_iam_policy_document.gene2fish_rnaquarium_read.json
}

# Attach this to the IAM role used by the Gene2Fish Kubernetes service account.
resource "aws_iam_role_policy_attachment" "gene2fish_rnaquarium_read" {
  role       = aws_iam_role.gene2fish_service_account.name
  policy_arn = aws_iam_policy.gene2fish_rnaquarium_read.arn
}

data "aws_iam_policy_document" "gene2fish_rnaquarium_write" {
  statement {
    sid = "ListGene2FishPrefix"

    actions = [
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.rnaquarium.arn,
    ]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "${local.gene2fish_prefix}/*",
      ]
    }
  }

  statement {
    sid = "WriteGene2FishObjects"

    actions = [
      "s3:PutObject",
      "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.rnaquarium.arn}/${local.gene2fish_prefix}/data/*",
      "${aws_s3_bucket.rnaquarium.arn}/${local.gene2fish_prefix}/zfin-images/*",
    ]
  }
}

resource "aws_iam_policy" "gene2fish_rnaquarium_write" {
  name   = "gene2fish-rnaquarium-write"
  policy = data.aws_iam_policy_document.gene2fish_rnaquarium_write.json
}

# Attach this only to the CI/manual uploader role that runs zfin_image_mirror.py
# and uploads refreshed image_metadata_v2.json/gene_aliases.json.
resource "aws_iam_role_policy_attachment" "gene2fish_rnaquarium_write" {
  role       = aws_iam_role.gene2fish_data_uploader.name
  policy_arn = aws_iam_policy.gene2fish_rnaquarium_write.arn
}
```

## App Configuration

The app deploy should receive:

```yaml
GENE2IMAGE_DATA_S3_BUCKET: czbsf-rnaquarium
GENE2IMAGE_DATA_S3_PREFIX: gene2fish/data
GENE2IMAGE_DATA_S3_REGION: us-west-2
GENE2IMAGE_IMAGE_S3_BUCKET: czbsf-rnaquarium
GENE2IMAGE_IMAGE_S3_PREFIX: gene2fish/zfin-images
GENE2IMAGE_IMAGE_S3_REGION: us-west-2
```

