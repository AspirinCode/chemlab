"""Test core types like Molecule and Atom."""
from chemlab.core.system import Molecule, Atom
from chemlab.core import System, subsystem_from_molecules, subsystem_from_atoms
from chemlab.core import merge_systems
from chemlab.core import crystal, random_lattice_box
import numpy as np
from nose.tools import eq_, assert_equals
from nose.plugins.attrib import attr
#from chemlab.graphics import display_system
from .testtools import assert_npequal, assert_eqbonds, assert_allclose

def _make_water():
    mol = Molecule([Atom("O", [-4.99, 2.49, 0.0]),
                    Atom("H", [-4.02, 2.49, 0.0]),
                    Atom("H", [-5.32, 1.98, 1.0])],
                   bonds=[[0, 1], [0, 2]],
                   export={'hello': 1.0})
    return mol

class TestAtom(object):
    def test_init(self):
        a = Atom("O", [-4.99, 2.49, 0.0])
        eq_(a.type_array, 'O')
        eq_(a.get_attribute('type_array').value, 'O')
        assert_npequal(a.r_array, [-4.99, 2.49, 0.0])
        eq_(a.get_attribute('r_array').value, [-4.99, 2.49, 0.0])

class TestMolecule(object):
    def test_init(self):
        mol = _make_water()
        eq_(mol.export, {'hello': 1.0})
        assert_npequal(mol.get_attribute('type_array').value, ['O', 'H', 'H'])
        assert_npequal(mol.type_array, ['O', 'H', 'H'])
        assert_npequal(mol.bonds, [[0, 1], [0, 2]])
        
        mol = Molecule.empty()
        eq_(mol.dimensions['atom'], 0)
        eq_(mol.dimensions['bond'], 0)

    def test_copy(self):
        mol = _make_water()
        mol2 = mol.copy()
        assert_npequal(mol2.type_array, mol.type_array)
        
class TestSystem(object):
    def _make_molecules(self):
        wat = _make_water()
        wat.r_array *= 0.1
        # Initialization from empty
        s = System.empty(4, 4*3)

        mols = []
        # Array to be compared
        for _ in range(s.n_mol):
            wat.r_array += 0.1
            mols.append(wat.copy())
        return mols

    def _assert_init(self, system):
        assert_npequal(system.type_array, ['O', 'H', 'H',
                                           'O', 'H', 'H',
                                           'O', 'H', 'H',
                                           'O', 'H', 'H',])

        # Test atom coordinates
        #print "Atom Coordinates"
        #print s.r_array

        # Test atom masses
        #print s.m_array

        # Test charges
        assert_allclose(system.charge_array, [0.0, 0.0, 0.0,
                                              0.0, 0.0, 0.0,
                                              0.0, 0.0, 0.0,
                                              0.0, 0.0, 0.0])

        # Test mol indices
        assert_npequal(system.mol_indices, [0, 3, 6, 9])

        # Test mol n_atoms
        assert_npequal(system.mol_n_atoms, [3, 3, 3, 3])

        # Test get molecule entry
        assert_npequal(system.molecules[0].type_array, ['O', 'H', 'H'])

        # Test bonds
        assert_eqbonds(system.bonds, [[0, 1], [0, 2],
                                      [3, 4], [3, 5],
                                      [6, 7], [6, 8],
                                      [9, 10], [9, 11]])

    def test_init(self):
        mols = self._make_molecules()
        system = System(mols)
        self._assert_init(system)

    # def test_from_empty(self):
    #     mols = self._make_molecules()
    #     system = System.empty(4, 4*3)
    #     [system.add(mol) for mol in mols]
    #     self._assert_init(system)
    
    def test_from_batch(self):
        mols = self._make_molecules()
        
        system = System()
        with system.batch() as batch:            
            [batch.append(mol) for mol in mols]
        self._assert_init(system)

    def test_from_actual_empty(self):
        mols = self._make_molecules()
        system = System([])
        [system.add(mol) for mol in mols]
        self._assert_init(system)

    def test_from_arrays(self):
        mols = self._make_molecules()
        r_array = np.concatenate([m.r_array for m in mols])
        type_array = np.concatenate([m.type_array for m in mols])
        mol_indices = [0, 3, 6, 9]
        bonds = np.concatenate([m.bonds + 3*i for i, m in enumerate(mols)])

        system = System.from_arrays(r_array=r_array,
                                    type_array=type_array,
                                    mol_indices=mol_indices,
                                    bonds=bonds)

        self._assert_init(system)

    def test_subsystem_from_molecules(self):
        mols = self._make_molecules()
        system = System(mols)
        
        subsystem = subsystem_from_molecules(system, np.array([0, 2]))
        assert_equals(subsystem.n_mol, 2)

    def test_subsystem_from_atoms(self):
        mols = self._make_molecules()
        system = System(mols)
        sub = subsystem_from_atoms(system, np.array([True, True, False,
                                                     False, False, False,
                                                     False, False, False]))
        assert_equals(sub.n_mol, 1)

    def test_remove_atoms(self):
        # This will remove the first and last molecules
        mols = self._make_molecules()
        system = System(mols)
        system.remove_atoms([0, 1, 11])

        assert_eqbonds(system.bonds,
                       [[0, 1], [0, 2],
                        [3, 4], [3, 5]])
        assert_npequal(system.type_array,
                       np.array(['O', 'H', 'H', 'O', 'H', 'H'],
                                dtype='object'))

    def test_reorder_molecules(self):
        mols = self._make_molecules()
        system = System(mols)
        system.bonds = np.array([[0, 1], [3, 5]])
        # Reordering
        system.reorder_molecules([1, 0, 2, 3])
        assert_eqbonds(system.bonds, [[0, 2],
                                      [3, 4]])


@attr('slow')
def test_merge_system():
    # take a protein
    from chemlab.io import datafile
    from chemlab.graphics import display_system

    from chemlab.db import ChemlabDB

    water = ChemlabDB().get("molecule", "example.water")

    prot = datafile("tests/data/3ZJE.pdb").read("system")

    # Take a box of water
    NWAT = 50000
    bsize = 20.0
    pos = np.random.random((NWAT, 3)) * bsize
    wat = water.copy()

    s = System()
    with s.batch() as b:
        s.append(wat)

    prot.r_array += 10
    s = merge_systems(s, prot, 0.5)

    display_system(s, 'ball-and-stick')


def test_crystal():
    '''Building a crystal by using spacegroup module'''
    na = Molecule([Atom('Na', [0.0, 0.0, 0.0])])
    cl = Molecule([Atom('Cl', [0.0, 0.0, 0.0])])

    # Fract position of Na and Cl, space group 255
    tsys = crystal([[0.0, 0.0, 0.0],[0.5, 0.5, 0.5]], [na, cl], 225, repetitions=[13,13,13])
    eq_(tsys.r_array.min(), 0.0)
    eq_(tsys.r_array.max(), 12.5)

def test_sort():
    na = Molecule([Atom('Na', [0.0, 0.0, 0.0])])
    cl = Molecule([Atom('Cl', [0.0, 0.0, 0.0])])

    # Fract position of Na and Cl, space group 255
    tsys = crystal([[0.0, 0.0, 0.0],[0.5, 0.5, 0.5]], [na, cl], 225, repetitions=[3,3,3])
    
    tsys.sort()
    assert_npequal(tsys.type_array[:tsys.n_mol/2], ['Cl'] * (tsys.n_mol/2))


def test_bonds():
    # TODO: deprecate this shit
    from chemlab.io import datafile
    bz = datafile("tests/data/benzene.mol").read('molecule')
    na = Molecule([Atom('Na', [0.0, 0.0, 0.0])])

    # Adding bonds
    s = System()
    with s.batch() as b:
        b.append(bz)
    
    assert_npequal(s.bonds, bz.bonds)
    assert_npequal(bz.bond_orders, [1, 2, 2, 1, 1, 2])
    assert_npequal(s.bond_orders, bz.bond_orders)

    s.add(bz)
    assert_npequal(s.type_array, ['C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C'])
    eq_(s.dimensions['atom'], 12)
    assert_npequal(s.bonds, np.concatenate((bz.bonds, bz.bonds + 7)))
    
    # Reordering
    s.bonds = np.array([[0, 1], [6, 8]])    
    s.reorder_molecules([1, 0])
    assert_eqbonds(s.bonds, np.array([[6, 7], [0, 2]]))
    
    # Selection
    ss = subsystem_from_molecules(s, [1])
    assert_npequal(ss.bonds, np.array([[0, 1]]))

def test_bond_orders():
    # Get a molecule with some bonds
    wat = _make_water()
    wat_o = wat.copy()
    # 0,1 0,2
    assert_npequal(wat.bond_orders, np.array([0, 0]))

    # Remove a bond
    wat.bonds = np.array([[0, 1]])
    assert_npequal(wat.bond_orders, np.array([0]))

    wat.bond_orders = np.array([2])

    # Try with a system
    s = System()

    s.add(wat_o)
    s.add(wat)

    assert_npequal(s.bond_orders , np.array([0, 0, 2]))
    s.reorder_molecules([1, 0])
    # Bonds get sorted accordingly
    assert_npequal(s.bond_orders , np.array([2, 0, 0]))

    s.bonds = np.array([[0, 1], [0, 2], [3, 4], [3, 5]])
    assert_npequal(s.bond_orders, np.array([2, 0, 0, 0]))

def test_random():
    '''Testing random made box'''
    from chemlab.db import ChemlabDB
    cdb = ChemlabDB()
    na = Molecule([Atom('Na', [0.0, 0.0, 0.0])])
    cl = Molecule([Atom('Cl', [0.0, 0.0, 0.0])])
    wat = cdb.get("molecule", 'gromacs.spce')

    s = random_lattice_box([na, cl, wat], [160, 160, 160], [4, 4, 4])

    #display_system(s)


def test_bond_guessing():
    from chemlab.db import ChemlabDB, CirDB
    from chemlab.graphics import display_molecule
    from chemlab.io import datafile

    mol = datafile('tests/data/3ZJE.pdb').read('molecule')
    print(mol.r_array)
    mol.guess_bonds()
    assert mol.bonds.size > 0

    # We should find the bond guessing also for systems

    # System Made of two benzenes
    bz = datafile("tests/data/benzene.mol").read('molecule')
    bzbonds = bz.bonds
    bz.bonds = np.array([])

    # Separating the benzenes by large amount
    bz2 = bz.copy()
    bz2.r_array += 2.0

    s = System([bz, bz2])
    s.guess_bonds()
    assert_eqbonds(s.bonds, np.concatenate((bzbonds, bzbonds + 6)))

    # Separating benzenes by small amount
    bz2 = bz.copy()
    bz2.r_array += 0.15

    s = System([bz, bz2])
    s.guess_bonds()
    assert_eqbonds(s.bonds, np.concatenate((bzbonds, bzbonds + 6)))

    #display_molecule(mol)

def test_serialization():
    cl = Molecule([Atom.from_fields(type='Cl', r=[0.0, 0.0, 0.0])])
    jsonstr =  cl.tojson()
    assert Molecule.from_json(jsonstr).tojson() == jsonstr

    na = Molecule([Atom('Na', [0.0, 0.0, 0.0])])
    cl = Molecule([Atom('Cl', [0.0, 0.0, 0.0])])

    # Fract position of Na and Cl, space group 255
    tsys = crystal([[0.0, 0.0, 0.0],[0.5, 0.5, 0.5]], [na, cl], 225, repetitions=[3,3,3])
    jsonstr = tsys.tojson()

    assert System.from_json(jsonstr).tojson() == jsonstr
