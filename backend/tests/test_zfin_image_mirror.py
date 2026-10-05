"""Guard the S3 mirror seeding script (GEN-22, GEN-45).

The mirror must hold exactly the Thisse image package ZFIN provided: legal
cleared us to host those images, and rights for other ZFIN images are case by
case. So the script uploads only from that package, never downloads from
zfin.org, and refuses to upload anything when the package holds a file outside
the five Thisse publications or the layout the backend maps to S3 keys.
"""

import io
import socket
import sys
import tarfile
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
import zfin_image_mirror  # noqa: E402

PREFIX = "gene2fish/zfin-images"
PUBS = "opt/zfin/loadUp/pubs"


def _package(tmp_path, files):
    """Write an uncompressed tar shaped like ZFIN's thisse-images.tar."""
    path = tmp_path / "thisse-images.tar"
    with tarfile.open(path, "w") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


class _FakeS3:
    def __init__(self, existing=(), fail_puts=False):
        self.existing = list(existing)
        self.fail_puts = fail_puts
        self.listed = []
        self.puts = {}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        fake = self

        class _Paginator:
            def paginate(self, Bucket, Prefix):
                fake.listed.append((Bucket, Prefix))
                yield {"Contents": [{"Key": k} for k in fake.existing if k.startswith(Prefix)]}

        return _Paginator()

    def put_object(self, Bucket, Key, Body, ContentType):
        if self.fail_puts:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject")
        self.puts[Key] = (Bucket, Body, ContentType)


@pytest.fixture
def s3(monkeypatch):
    # Seeding must never reach zfin.org (or anywhere but the faked S3 client).
    def boom(*args, **kwargs):
        raise AssertionError("the mirror script must not open network connections")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)

    def install(fake):
        monkeypatch.setattr(zfin_image_mirror.boto3, "client", lambda *a, **k: fake)
        return fake

    return install


VALID = {
    f"{PUBS}/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888.jpg": b"plain",
    f"{PUBS}/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888_medium.jpg": b"medium",
    f"./{PUBS}/2001/ZDB-PUB-010810-1/ZDB-IMAGE-021202-261_annot.jpg": b"annot",
}


def test_member_key_maps_package_paths_to_mirror_keys():
    assert zfin_image_mirror.member_key(
        f"{PUBS}/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888_medium.jpg", PREFIX
    ) == f"{PREFIX}/imageLoadUp/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888_medium.jpg"
    assert zfin_image_mirror.member_key(
        f"./{PUBS}/2001/ZDB-PUB-010810-1/ZDB-IMAGE-021202-261_annot_medium.jpg", PREFIX + "/"
    ) == f"{PREFIX}/imageLoadUp/2001/ZDB-PUB-010810-1/ZDB-IMAGE-021202-261_annot_medium.jpg"


@pytest.mark.parametrize(
    "name",
    [
        f"{PUBS}/2006/ZDB-PUB-060503-2/ZDB-IMAGE-981125-4_medium.jpg",  # not a Thisse publication
        f"{PUBS}/2005/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888.jpg",  # year dir doesn't match the pub
        f"{PUBS}/2004/ZDB-PUB-040907-1/notes.txt",
        f"{PUBS}/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888.png",
        f"{PUBS}/2004/ZDB-PUB-040907-1/extra/ZDB-IMAGE-060810-2888.jpg",
        f"{PUBS}/2004/ZDB-PUB-040907-1/../ZDB-PUB-060503-2/ZDB-IMAGE-981125-4.jpg",
        "ZDB-IMAGE-060810-2888.jpg",
    ],
)
def test_member_key_rejects_anything_outside_the_thisse_package(name):
    with pytest.raises(ValueError):
        zfin_image_mirror.member_key(name, PREFIX)


def test_uploads_only_package_images_missing_from_the_mirror(tmp_path, s3):
    already = f"{PREFIX}/imageLoadUp/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888.jpg"
    fake = s3(_FakeS3(existing=[already]))
    package = _package(tmp_path, VALID)

    rc = zfin_image_mirror.main(["--package", str(package), "--bucket", "mirror-bucket"])

    assert rc == 0
    assert fake.listed == [("mirror-bucket", f"{PREFIX}/")]
    assert fake.puts == {
        f"{PREFIX}/imageLoadUp/2004/ZDB-PUB-040907-1/ZDB-IMAGE-060810-2888_medium.jpg": (
            "mirror-bucket", b"medium", "image/jpeg"
        ),
        f"{PREFIX}/imageLoadUp/2001/ZDB-PUB-010810-1/ZDB-IMAGE-021202-261_annot.jpg": (
            "mirror-bucket", b"annot", "image/jpeg"
        ),
    }


def test_dry_run_reports_without_uploading(tmp_path, s3, capsys):
    fake = s3(_FakeS3())
    package = _package(tmp_path, VALID)

    rc = zfin_image_mirror.main(["--package", str(package), "--bucket", "mirror-bucket", "--dry-run"])

    assert rc == 0
    assert fake.puts == {}
    assert "would upload 3" in capsys.readouterr().out


def test_refuses_the_whole_package_if_any_member_is_unexpected(tmp_path, s3):
    # Fail closed: one non-Thisse image means the wrong file was given, so
    # nothing is uploaded at all (not even the valid members before it).
    fake = s3(_FakeS3())
    package = _package(
        tmp_path,
        {**VALID, f"{PUBS}/2006/ZDB-PUB-060503-2/ZDB-IMAGE-981125-4_medium.jpg": b"other"},
    )

    with pytest.raises(SystemExit) as exc:
        zfin_image_mirror.main(["--package", str(package), "--bucket", "mirror-bucket"])

    assert "ZDB-PUB-060503-2" in str(exc.value)
    assert fake.puts == {}
    assert fake.listed == []


def test_refuses_an_empty_package(tmp_path, s3):
    fake = s3(_FakeS3())
    package = _package(tmp_path, {})

    with pytest.raises(SystemExit):
        zfin_image_mirror.main(["--package", str(package), "--bucket", "mirror-bucket"])

    assert fake.puts == {}


def test_upload_failures_exit_non_zero(tmp_path, s3):
    s3(_FakeS3(fail_puts=True))
    package = _package(tmp_path, VALID)

    rc = zfin_image_mirror.main(["--package", str(package), "--bucket", "mirror-bucket"])

    assert rc == 1


def test_bucket_is_required(tmp_path, s3):
    # No default bucket: a forgotten flag must not seed some other bucket.
    s3(_FakeS3())
    package = _package(tmp_path, VALID)

    with pytest.raises(SystemExit):
        zfin_image_mirror.main(["--package", str(package)])
