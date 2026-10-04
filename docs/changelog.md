# Changelog

Crates changes will be documented on this page.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

---

## [0.1.0b3] <small>- 2026-10-04</small>

### Added

- `Plugin.unload` now logs when a plugin is unregistered.
- Added Plugin's package installation entry to the project's README file for those who can't visit the website.

### Changed

- Improved docstring for `Plugin.unload`.
- Improved type checking and docstring for `Plugin.before` and `Plugin.after` hooks.

### Fixed

- Fixed plugin unloading only removing plugin hooks and not unregistering the plugin.

---

## [0.1.0b2] <small>- 2026-10-01</small>

### Added

- Added `CatchRowOverride` and `CountryballNamePromptOverride` components, providing hookable catch row and prompt behavior.
- Added docstring to the following methods:
    - `get_component`
    - `BallSpawnViewOverride.get_spawn_message`
    - `BallSpawnViewOverride.send_spawn`
    - `BallSpawnViewOverride.spawn`
    - `BallSpawnViewOverride.resolve_player`
    - `BallSpawnViewOverride.return_to_owner`
    - `BallSpawnViewOverride.transfer_existing`
    - `BallSpawnViewOverride.hand_over_existing`
    - `BallSpawnViewOverride.record_metrics`
    - `BallSpawnVIewOverride.get_catch_message`
- Added overloads and return types to `get_component`.
- Added `Hookable` and `HookableCoroutine` types.

### Changed

- Renamed the "BallSpawnViewOverride" docs page to "Countryballs".
- `PluginConflict` is now private and no longer appears in the API reference.
- Improved type checking internally.

### Fixed

- Fixed `plugin.get` not being exported from the plugins module.
- Fixed `hookable` typing async callbacks as `Awaitable` instead of `Coroutine`.
- Fixed `Plugin.before` and `Plugin.after` hooks raising a type error for hookable methods.
- Fixed an incorrect logger path in `plugin/modules/components/countryballs/views.py`.
- Resolved various other type errors.

---

## [0.1.0b1] <small>- 2026-09-29</small>

- Initial Plugin beta release.


[Unreleased]: https://github.com/Caylies/Plugin/compare/0.1.0b3...HEAD
[0.1.0b3]: https://github.com/Caylies/Plugin/releases/tag/0.1.0b3
[0.1.0b2]: https://github.com/Caylies/Plugin/releases/tag/0.1.0b2
[0.1.0b1]: https://github.com/Caylies/Plugin/releases/tag/0.1.0b1
