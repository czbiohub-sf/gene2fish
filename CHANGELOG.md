# Changelog

## [0.9.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.8.0...v0.9.0) (2026-08-13)


### Features

* track per-image Plausible views (GEN-40) ([#126](https://github.com/czbiohub-sf/gene2fish/issues/126)) ([0973002](https://github.com/czbiohub-sf/gene2fish/commit/0973002cb0305e1f68246a602288ad84f0d26363))

## [0.8.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.7.0...v0.8.0) (2026-08-11)


### Features

* report backend errors to Sentry (GEN-37) ([#119](https://github.com/czbiohub-sf/gene2fish/issues/119)) ([d788c40](https://github.com/czbiohub-sf/gene2fish/commit/d788c40c45bed123b87ff67b3f4f71430b074aef))
* report frontend errors to Sentry (GEN-37) ([#121](https://github.com/czbiohub-sf/gene2fish/issues/121)) ([6e0e475](https://github.com/czbiohub-sf/gene2fish/commit/6e0e475f397ddb2d1e0e74e98dce4ff6bb86b439))

## [0.7.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.6.3...v0.7.0) (2026-08-11)


### Features

* **security:** batch limits, slim runtime image, security headers & CI hardening (GEN-4/5/6/7/8) ([#113](https://github.com/czbiohub-sf/gene2fish/issues/113)) ([70797f4](https://github.com/czbiohub-sf/gene2fish/commit/70797f44f4ce59247e58244e742452ec78394a40))

## [0.6.3](https://github.com/czbiohub-sf/gene2fish/compare/v0.6.2...v0.6.3) (2026-08-07)


### Bug Fixes

* **images:** serve medium-res grid images instead of tiny thumbnails (GEN-36) ([#108](https://github.com/czbiohub-sf/gene2fish/issues/108)) ([7acaad8](https://github.com/czbiohub-sf/gene2fish/commit/7acaad8a3747854d2b8fd8f69c3e05a3b150b59f))

## [0.6.2](https://github.com/czbiohub-sf/gene2fish/compare/v0.6.1...v0.6.2) (2026-07-18)


### Bug Fixes

* **images:** remove the 150ms grid load throttle now that cells use thumbnails ([#84](https://github.com/czbiohub-sf/gene2fish/issues/84)) ([0a32d23](https://github.com/czbiohub-sf/gene2fish/commit/0a32d2376346fcf9b494c4b3172b6e5fe165f8f9))

## [0.6.1](https://github.com/czbiohub-sf/gene2fish/compare/v0.6.0...v0.6.1) (2026-07-18)


### Bug Fixes

* **image-proxy:** fall back to plain .jpg when ZFIN lacks the annotated variant ([#81](https://github.com/czbiohub-sf/gene2fish/issues/81)) ([f77f84f](https://github.com/czbiohub-sf/gene2fish/commit/f77f84fe0506588c9ea58b0ea2949596730ed7e1))

## [0.6.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.5.0...v0.6.0) (2026-07-15)


### Features

* **analytics:** add Plausible tracking snippet (GEN-28) ([#77](https://github.com/czbiohub-sf/gene2fish/issues/77)) ([448aed4](https://github.com/czbiohub-sf/gene2fish/commit/448aed4dec6bf1748915f1e0cd69267c857d9884))
* **filters:** make stage/anatomy options context-aware (GEN-23) ([#70](https://github.com/czbiohub-sf/gene2fish/issues/70)) ([5f9cfad](https://github.com/czbiohub-sf/gene2fish/commit/5f9cfad54de546cd31cd189d4a937750113666c8))
* **frontend:** add favicon for gene2fish (GEN-25) ([#69](https://github.com/czbiohub-sf/gene2fish/issues/69)) ([4809990](https://github.com/czbiohub-sf/gene2fish/commit/4809990111859ec80aec287760127fc01dbae481))
* **references:** add ZFIN knowledgebase citation (GEN-30) ([#76](https://github.com/czbiohub-sf/gene2fish/issues/76)) ([ed5058e](https://github.com/czbiohub-sf/gene2fish/commit/ed5058ef260fde2fcef7288fcca3ddd8d99adccb))
* switch prod access from Okta to basic auth for external demos (CNTR-101) ([#59](https://github.com/czbiohub-sf/gene2fish/issues/59)) ([3c99592](https://github.com/czbiohub-sf/gene2fish/commit/3c99592bd6e1f47f5f431d3303f5a7fb4136db6a))


### Bug Fixes

* **ci:** remove dependabot auto-merge to require human review ([#65](https://github.com/czbiohub-sf/gene2fish/issues/65)) ([5ee201a](https://github.com/czbiohub-sf/gene2fish/commit/5ee201a554e19ea4dbf06416d18c6db8147c8134))
* **cors:** drop localhost dev origins from deployed environments ([#67](https://github.com/czbiohub-sf/gene2fish/issues/67)) ([42b1fe7](https://github.com/czbiohub-sf/gene2fish/commit/42b1fe7399630ea6eb9dbc5a9950cfc68356e1e8))
* **image-proxy:** refuse redirects when fetching ZFIN images (SSRF) ([#66](https://github.com/czbiohub-sf/gene2fish/issues/66)) ([5177701](https://github.com/czbiohub-sf/gene2fish/commit/5177701950a8d02d06d32f755a61c8c8653a8592))
* **image-proxy:** reject non-image content and add nosniff (XSS) ([#68](https://github.com/czbiohub-sf/gene2fish/issues/68)) ([1fc4c52](https://github.com/czbiohub-sf/gene2fish/commit/1fc4c5231b2ff378f68711f95364398196140e22))

## [0.5.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.4.0...v0.5.0) (2026-06-25)


### Features

* serve ZFIN images from our own S3 mirror to survive ZFIN outages (GEN-22) ([#49](https://github.com/czbiohub-sf/gene2fish/issues/49)) ([0d3a926](https://github.com/czbiohub-sf/gene2fish/commit/0d3a926648140ae16edb7afa4628add98637a1ea))

## [0.4.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.3.1...v0.4.0) (2026-06-23)


### Features

* support gene search by previous and alias names (GEN-18) ([#46](https://github.com/czbiohub-sf/gene2fish/issues/46)) ([542f4b5](https://github.com/czbiohub-sf/gene2fish/commit/542f4b5c762421321b8dfcc922168361780acf20))

## [0.3.1](https://github.com/czbiohub-sf/gene2fish/compare/v0.3.0...v0.3.1) (2026-06-19)


### Bug Fixes

* show no-image feedback in empty gene cells ([#37](https://github.com/czbiohub-sf/gene2fish/issues/37)) ([3eb93bd](https://github.com/czbiohub-sf/gene2fish/commit/3eb93bd4e99b767df05500ebed7ec1b0c429c993))

## [0.3.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.2.0...v0.3.0) (2026-06-12)


### Features

* update anatomy filters and table export ([#34](https://github.com/czbiohub-sf/gene2fish/issues/34)) ([b5443b9](https://github.com/czbiohub-sf/gene2fish/commit/b5443b95f1a68203ad30881a5421b6996b563448))

## [0.2.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.1.0...v0.2.0) (2026-06-03)


### Features

* build top-level layout and filters ([#25](https://github.com/czbiohub-sf/gene2fish/issues/25)) ([1991080](https://github.com/czbiohub-sf/gene2fish/commit/19910802d54986249e6607769b0abaac1cca98d3))

## [0.1.0](https://github.com/czbiohub-sf/gene2fish/compare/v0.0.1...v0.1.0) (2026-05-30)


### Features

* adding version version of the image extractor ([d3731ca](https://github.com/czbiohub-sf/gene2fish/commit/d3731caedbf5e60a12e62058cb22a2465ddd1cf0))
* initial app build with extractor fixes ([5858331](https://github.com/czbiohub-sf/gene2fish/commit/5858331a2589d066e9a2bbb5c7af01f6ba8ddb1d))


### Bug Fixes

* **deps:** bump starlette to 1.2.0 and idna to 3.17 to patch CVEs (GEN-2) ([#8](https://github.com/czbiohub-sf/gene2fish/issues/8)) ([5a5cf50](https://github.com/czbiohub-sf/gene2fish/commit/5a5cf50b53db4ae24fdfc1fdb37124b09d158d2d))
* **infra:** use ingress.rules instead of host scalar for prod/staging ([#7](https://github.com/czbiohub-sf/gene2fish/issues/7)) ([96945a8](https://github.com/czbiohub-sf/gene2fish/commit/96945a8833f469daf52b53efe6f582f46f9e0d40))
