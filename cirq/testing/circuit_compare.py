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

from typing import Tuple, Sequence, TYPE_CHECKING, Optional, Any

import itertools
import numpy as np

from cirq import circuits, ops, linalg, protocols

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from typing import Set


def _cancel_qubit_phase(m1: np.ndarray,
                        m2: np.ndarray,
                        qubits: Sequence[int]
                        ) -> None:
    """Makes the two matrices more similar by phasing qubits in ks.

    This method mutates the given matrices.

    Works by creating a linear problem of the form:

        m0 + m1 + m2 + m3 = d_000
           + m1 + m2 + m3 = d_001
        m0 +    + m2 + m3 = d_010
           +    + m2 + m3 = d_011
        m0 + m1 +    + m3 = d_100
           + m1 +    + m3 = d_101
        m0 +    +    + m3 = d_110
           +    +    + m3 = d_111

        - each d_r is the dominant phase difference of row r in each matrix
        - each m_k column is a qubit phasing operation; included only if k in ks

    The linear problem is then solved, and the m_k values are used to apply
    qubit phasing operations that should turn one matrix into the other.

    Args:
        m1: A unitary matrix.
        m2: Another unitary matrix.
        qubits: Indices of the qubit we are allowed to phase.
            'Out of range' qubits correspond to global phasing.
    """

    n = m1.shape[0]
    assert m1.shape == m2.shape == (n, n)

    prob = np.zeros(shape=(n, len(qubits) + 1))

    # Measurement phase coefficients.
    for i, k in enumerate(qubits):
        for row in range(n):
            prob[row, i] = 0 if row & (1 << k) else 1

    # Dominant row phase differences.
    for row in range(n):
        col = max(range(n), key=lambda c: min(
            abs(m1[row, c]), abs(m2[row, c])))
        prob[row, -1] = np.angle(m1[row, col]) - np.angle(m2[row, col])

    # Gram-Schmidt.
    used = set()  # type: Set[int]
    for col in range(len(qubits)):
        chosen_row = min(row for row in range(n)
                         if row not in used and prob[row, col])
        used.add(chosen_row)
        prob[chosen_row, :] /= prob[chosen_row, col]
        for row in range(n):
            if row != chosen_row:
                prob[row, :] -= prob[row, col] * prob[chosen_row, :]

    # Extract and apply phase correction solutions.
    for col, k in enumerate(qubits):
        chosen_row = max(range(n), key=lambda r: prob[r, col])
        adjust = np.exp(1j * prob[chosen_row, -1])
        for row in range(n):
            if row & (1 << k):
                m1[row, :] *= adjust


def _canonicalize_up_to_terminal_measurement_phase(
        circuit1: circuits.Circuit,
        circuit2: circuits.Circuit) -> Tuple[np.ndarray, np.ndarray]:
    qubits = circuit1.all_qubits().union(circuit2.all_qubits())
    order = sorted(qubits)[::-1]
    assert circuit1.are_all_measurements_terminal()
    assert circuit2.are_all_measurements_terminal()

    measured_1 = {q
                  for op in circuit1.all_operations()
                  if ops.MeasurementGate.is_measurement(op)
                  for q in op.qubits}
    measured_2 = {q
                  for op in circuit2.all_operations()
                  if ops.MeasurementGate.is_measurement(op)
                  for q in op.qubits}
    assert measured_1 == measured_2

    matrix1 = circuit1.to_unitary_matrix(qubits_that_should_be_present=qubits)
    matrix2 = circuit2.to_unitary_matrix(qubits_that_should_be_present=qubits)
    ks = [len(order)]
    for q in measured_1:
        ks.append(order.index(q))
    _cancel_qubit_phase(matrix1, matrix2, ks)
    return matrix1, matrix2


def highlight_text_differences(actual: str, expected: str) -> str:
    diff = ""
    for actual_line, desired_line in itertools.zip_longest(
            actual.splitlines(), expected.splitlines(),
            fillvalue=""):
        diff += "".join(a if a == b else "█"
                        for a, b in itertools.zip_longest(
                            actual_line, desired_line, fillvalue="")) + "\n"
    return diff


def assert_circuits_with_terminal_measurements_are_equivalent(
        actual: circuits.Circuit,
        reference: circuits.Circuit,
        atol: float) -> None:
    """Determines if two circuits have equivalent effects.

    The circuits can contain measurements, but the measurements must be at the
    end of the circuit. Circuits are equivalent if, for all possible inputs,
    their outputs (both classical via measurements and quantum via
    not-measurements) are observationally indistinguishable up to a tolerance.

    For example, applying an extra Z gate to an unmeasured qubit changes the
    effect of a circuit. But inserting a Z gate operation just before a
    measurement does not.

    Args:
        actual: The circuit that was actually computed by some process.
        reference: A circuit with the correct function.
        atol: Absolute error tolerance.
    """
    m1, m2 = _canonicalize_up_to_terminal_measurement_phase(actual, reference)

    assert linalg.allclose_up_to_global_phase(m1, m2, atol=atol), (
        "Circuit's effect differs from the reference circuit.\n"
        '\n'
        'Diagram of actual circuit:\n'
        '{}\n'
        '\n'
        'Diagram of reference circuit with desired function:\n'
        '{}\n'.format(actual, reference)
    )


def assert_same_circuits(actual: circuits.Circuit,
                         expected: circuits.Circuit,
                         ) -> None:
    """Asserts that two circuits are identical, with a descriptive error.

    Args:
        actual: A circuit computed by some code under test.
        expected: The circuit that should have been computed.
    """
    assert actual == expected, (
        "Actual circuit differs from expected circuit.\n"
        "\n"
        "Diagram of actual circuit:\n"
        "{}\n"
        "\n"
        "Diagram of expected circuit:\n"
        "{}\n"
        "\n"
        "Index of first differing moment:\n"
        "{}\n"
        "\n"
        "Full repr of actual circuit:\n"
        "{!r}\n"
        "\n"
        "Full repr of expected circuit:\n"
        "{!r}\n").format(actual,
                         expected,
                         _first_differing_moment_index(actual, expected),
                         actual,
                         expected)


def _first_differing_moment_index(circuit1: circuits.Circuit,
                                  circuit2: circuits.Circuit) -> Optional[int]:
    for i, (m1, m2) in enumerate(itertools.zip_longest(circuit1, circuit2)):
        if m1 != m2:
            return i
    return None  # coverage: ignore


def assert_has_diagram(
        actual: circuits.Circuit,
        desired: str,
        **kwargs) -> None:
    """Determines if a given circuit has the desired text diagram.

    Args:
        actual: The circuit that was actually computed by some process.
        desired: The desired text diagram as a string. Whitespace at the
            beginning and end are ignored.
        **kwargs: Keyword arguments to be passed to actual.to_text_diagram().
    """
    actual_diagram = actual.to_text_diagram(**kwargs).strip()
    desired_diagram = desired.strip()
    assert actual_diagram == desired_diagram, (
        "Circuit's text diagram differs from the desired diagram.\n"
        '\n'
        'Diagram of actual circuit:\n'
        '{}\n'
        '\n'
        'Desired text diagram:\n'
        '{}\n'
        '\n'
        'Highlighted differences:\n'
        '{}\n'.format(actual_diagram, desired_diagram,
                      highlight_text_differences(actual_diagram,
                                                 desired_diagram))
    )


def _infer_qubit_count(val: Any) -> int:
    if isinstance(val, ops.Operation):
        return len(val.qubits)
    if isinstance(val, ops.SingleQubitGate):
        return 1
    if isinstance(val, ops.TwoQubitGate):
        return 2
    if isinstance(val, ops.ThreeQubitGate):
        return 3
    if isinstance(val, ops.ControlledGate):
        return 1 + _infer_qubit_count(val.sub_gate)
    raise NotImplementedError(
        'Failed to infer qubit count of <{!r}>. Specify it.'.format(val))


def assert_apply_unitary_to_tensor_is_consistent_with_unitary(
        val: Any,
        exponents: Sequence[Any] = (1,),
        qubit_count: Optional[int] = None) -> None:

    n = qubit_count if qubit_count is not None else _infer_qubit_count(val)

    for exponent in exponents:
        val_exp = val if exponent == 1 else val**exponent
        eye = np.eye(2 << n, dtype=np.complex128).reshape((2,) * (2 * n + 2))
        actual = protocols.apply_unitary_to_tensor(
            val=val_exp,
            target_tensor=eye,
            available_buffer=np.ones_like(eye) * float('nan'),
            axes=list(range(n)),
            default=None)
        expected = protocols.unitary(val_exp, default=None)

        # If you don't have a unitary, you shouldn't be able to apply a unitary.
        if expected is None:
            assert actual is None
        else:
            expected = np.kron(expected, np.eye(2))

        # If you applied a unitary, it should match the one you say you have.
        if actual is not None:
            np.testing.assert_allclose(
                actual.reshape(2 << n, 2 << n),
                expected)
