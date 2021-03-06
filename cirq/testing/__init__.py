# Copyright 2018 The Cirq Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities for testing code."""

from cirq.testing.circuit_compare import (
    assert_apply_unitary_to_tensor_is_consistent_with_unitary,
    assert_circuits_with_terminal_measurements_are_equivalent,
    assert_has_diagram,
    assert_same_circuits,
    highlight_text_differences,
)
from cirq.testing.equals_tester import (
    EqualsTester,
)
from cirq.testing.equivalent_repr_eval import (
    assert_equivalent_repr,
)
from cirq.testing.file_tester import (
    TempDirectoryPath,
    TempFilePath,
)
from cirq.testing.lin_alg_utils import (
    random_orthogonal,
    random_special_orthogonal,
    random_special_unitary,
    random_unitary,
    assert_allclose_up_to_global_phase,
)
from cirq.testing.order_tester import (
    OrderTester,
)
from cirq.testing.random_circuit import (
    random_circuit,
)
from cirq.testing.only_test_in_python3 import (
    only_test_in_python3,
)
from cirq.testing.sample_circuits import (
    nonoptimal_toffoli_circuit,
)
