# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""pyinstaller configuration for gcpdiag.lint."""

from PyInstaller.utils.hooks import collect_submodules

# update also bin/precommit-required-files
hiddenimports = \
  collect_submodules('gcpdiag.lint.apigee') + \
  collect_submodules('gcpdiag.lint.bigquery') + \
  collect_submodules('gcpdiag.lint.composer') + \
  collect_submodules('gcpdiag.lint.cloudsql') + \
  collect_submodules('gcpdiag.lint.datafusion') + \
  collect_submodules('gcpdiag.lint.dataproc') + \
  collect_submodules('gcpdiag.lint.gaes') + \
  collect_submodules('gcpdiag.lint.gcb') + \
  collect_submodules('gcpdiag.lint.gce') + \
  collect_submodules('gcpdiag.lint.gcf') + \
  collect_submodules('gcpdiag.lint.gke') + \
  collect_submodules('gcpdiag.lint.vpc') + \
  collect_submodules('gcpdiag.lint.iam') + \
  collect_submodules('gcpdiag.lint.tpu')
