# -----------------------------------------------------------------------------------------------------
# CONDOR
# Simulator for diffractive single-particle imaging experiments with X-ray lasers
# http://xfel.icm.uu.se/condor/
# -----------------------------------------------------------------------------------------------------
# Copyright 2014 Max Hantke, Filipe R.N.C. Maia, Tomas Ekeberg
# Condor is distributed under the terms of the GNU General Public License
# -----------------------------------------------------------------------------------------------------
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a pariticular purpose. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
# -----------------------------------------------------------------------------------------------------
# General note:
# All variables are in SI units by default. Exceptions explicit by variable name.
# -----------------------------------------------------------------------------------------------------

# System packages
import sys, numpy
import copy

# Logging
import logging
logger = logging.getLogger(__name__)
import condor.utils.log
from condor.utils.log import log 
from condor.utils.log import log_and_raise_error,log_warning,log_info,log_debug

# Constants
from scipy import constants

# Condor modules
import condor
from condor.utils.material import Material
from condor.utils.variation import Variation

import condor.utils.diffraction

class AbstractParticle:
    r"""
    Base class for every derived particle class

    Kwargs:
      :rotation_values: See :meth:`condor.particle.particle_abstract.AbstractParticle.set_alignment` (default ``None``)

      :rotation_formalism (str): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_alignment` (default ``None``)

      :rotation_mode (str): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_alignment` (default ``None``)

      :number_density (float): Number density of this particle species in units of the interaction volume. (defaukt ``1.``)

      :arrival (str): Arrival of particles at the interaction volume can be either ``'random'`` or ``'synchronised'``. If ``sync`` at every event the number of particles in the interaction volume equals the rounded value of the ``number_density``. If ``'random'`` the number of particles is Poissonian and the ``number_density`` is the expectation value. (default ``'synchronised'``)
    
      :position: (Mean) position vector [*x*, *y*, *z*] of the particle. If set to ``None`` the particle is placed at the origin (default ``None``)

      :position_variation (str): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_position_variation` (default ``None``)

      :position_spread (float): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_position_variation` (default ``None``)

      :position_variation_n (int): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_position_variation` (default ``None``)

    """
    def __init__(self,
                 rotation_values = None, rotation_formalism = None, rotation_mode = "extrinsic",
                 number_density = 1., arrival = "synchronised",
                 position = None,  position_variation = None, position_spread = None, position_variation_n = None):
        self.set_alignment(rotation_values=rotation_values, rotation_formalism=rotation_formalism, rotation_mode=rotation_mode)
        self.set_position_variation(position_variation=position_variation, position_spread=position_spread, position_variation_n=position_variation_n)
        self.position_mean = position if position is not None else [0., 0., 0.]
        self.number_density = number_density
        self.arrival = arrival

    def get_next_number_of_particles(self):
        """
        Iterate the number of partices
        """
        if self.arrival == "random":
            return int(numpy.random.poisson(self.number_density))
        elif self.arrival == "synchronised":
            return int(numpy.round(self.number_density))
        else:
            log_and_raise_error(logger, "self.arrival=%s is invalid. Has to be either \'synchronised\' or \'random\'." % self.arrival)
        
    def get_next(self):
        """
        Iterate the parameters of the Particle instance and return them as a dictionary
        """
        O = {}
        O["_class_instance"]      = self
        O["extrinsic_quaternion"] = self._get_next_extrinsic_rotation().get_as_quaternion()
        O["position"]             = self._get_next_position()
        return O

    def get_current_rotation(self):
        """
        Return current orientation of the particle in form of an instance of :class:`condor.utils.rotation.Rotation`
        """
        return self._rotations.get_current_rotation()

    def set_alignment(self, rotation_values, rotation_formalism, rotation_mode):
        """
        Set rotation scheme of the partice

        Args:        
          :rotation_values: Array of rotation parameters. For simulating patterns of many shots this can be also a sequence of rotation parameters. Input ``None`` for no rotation and for random rotation formalisms. For more documentation see :class:`condor.utils.rotation.Rotations` (default ``None``)  

          :rotation_mode (str): If the rotation shall be assigned to the particle choose ``\'extrinsic\'``. Choose ``\'intrinsic\'`` if the coordinate system shall be rotated (default ``\'extrinsic\'``)

        """
        # Check input
        if rotation_mode not in ["extrinsic","intrinsic"]:
            log_and_raise_error(logger, "%s is not a valid rotation mode for alignment." % rotation_mode)
            sys.exit(1)
        self._rotation_mode = rotation_mode
        self._rotations = condor.utils.rotation.Rotations(values=rotation_values, formalism=rotation_formalism)

    def set_position_variation(self, position_variation, position_spread, position_variation_n):
        r"""
        Set position variation scheme

        Args:
          :position_variation (str): Statistical variation of the particle position (default ``None``)

            *Choose one of the following options:*
        
            ====================== ============================================================================================
            ``position_variation`` Type of variation
            ====================== ============================================================================================
            ``None``               No positional variation
            ``'normal'``           Normal (*Gaussian*) variation
            ``'uniform'``          Uniformly distributed positions within spread limits
            ``'range'``            Equidistant sequence of ``position_variation_n`` position samples within ``position_spread``
            ====================== ============================================================================================

          :position_spread (float): Statistical spread of the particle position

          :position_variation_n (int): Number of position samples within the specified range in each dimension

            .. note:: The argument ``position_variation_n`` takes effect only in combination with ``position_variation='range'``
        """
        self._position_variation = Variation(position_variation,position_spread,position_variation_n,number_of_dimensions=3)

    
    def _get_next_extrinsic_rotation(self):
        rotation = self._rotations.get_next_rotation()
        if self._rotation_mode == "intrinsic":
            rotation = copy.deepcopy(rotation)
            rotation.invert()
        return rotation

    def _get_next_position(self):
        return self._position_variation.get(self.position_mean)
    
    def get_conf(self):
        """
        Get configuration in form of a dictionary
        """
        conf = {}
        conf.update(self._get_conf_rotation())
        conf.update(self._get_conf_position_variation())
        conf["number_density"] = self.number_density
        conf["arrival"]        = self.arrival
        return conf

    def _get_conf_alignment(self):
        R = self.get_current_rotation()
        A = {
            "rotation_values"    : self._rotations.get_all_values(),
            "rotation_formalism" : self._rotations.get_formalism(),
            "rotation_mode"      : self._rotation_mode
        }
        return A
    
    def _get_conf_position_variation(self):
        A = {
            "position_variation":        self._position_variation.get_mode(),
            "position_variation_spread": self._position_variation.get_spread(),
            "position_variation_n":      self._position_variation.n
        }
        return A
        

class AbstractContinuousParticle(AbstractParticle):
    """
    Base class for derived particle classes that make use of the continuum approximation (density instead of discrete atoms)

    Args:
      :diameter (float): (Mean) particle diameter in unit meter
    
    Kwargs:
      :diameter_variation (str): See :meth:`condor.particle.particle_abstract.AbstractContinuousParticle.set_diameter_variation` (default ``None``)

      :diameter_spread (float): See :meth:`condor.particle.particle_abstract.AbstractContinuousParticle.set_diameter_variation` (default ``None``)

      :diameter_variation_n (int): See :meth:`condor.particle.particle_abstract.AbstractContinuousParticle.set_diameter_variation` (default ``None``)

      :rotation_values (array): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_alignment` (default ``None``)

      :rotation_formalism (str): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_alignment` (default ``None``)

      :rotation_mode (str): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_alignment` (default ``None``)

      :number_density (float): Number density of this particle species in units of the interaction volume. (defaukt ``1.``)

      :arrival (str): Arrival of particles at the interaction volume can be either ``'random'`` or ``'synchronised'``. If ``sync`` at every event the number of particles in the interaction volume equals the rounded value of the ``number_density``. If ``'random'`` the number of particles is Poissonian and the ``number_density`` is the expectation value. (default ``'synchronised'``)

      :position (array): See :class:`condor.particle.particle_abstract.AbstractParticle` (default ``None``)

      :position_variation (str): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_position_variation` (default ``None``)

      :position_spread (float): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_position_variation` (default ``None``)

      :position_variation_n (int): See :meth:`condor.particle.particle_abstract.AbstractParticle.set_position_variation` (default ``None``)

      :material_type (str): See :meth:`condor.particle.particle_abstract.AbstractContinuousParticle.set_material` (default ``\'water\'``)

      :massdensity (float): See :meth:`condor.particle.particle_abstract.AbstractContinuousParticle.set_material` (default ``None``)

      :atomic_composition (dict): See :meth:`condor.particle.particle_abstract.AbstractContinuousParticle.set_material` (default ``None``)
    """
    def __init__(self,
                 diameter, diameter_variation = None, diameter_spread = None, diameter_variation_n = None,
                 rotation_values = None, rotation_formalism = None, rotation_mode = "extrinsic",
                 number_density = 1., arrival = "synchronised",
                 position = None,  position_variation = None, position_spread = None, position_variation_n = None,
                 material_type = 'water', massdensity = None, atomic_composition = None):
        
        # Initialise base class
        AbstractParticle.__init__(self,
                                  rotation_values=rotation_values, rotation_formalism=rotation_formalism, rotation_mode=rotation_mode,
                                  number_density=number_density, arrival=arrival,
                                  position=position, position_variation=position_variation, position_spread=position_spread, position_variation_n=position_variation_n)
        # Diameter
        self.set_diameter_variation(diameter_variation=diameter_variation, diameter_spread=diameter_spread, diameter_variation_n=diameter_variation_n)
        self.diameter_mean = diameter
        # Material
        self.set_material(material_type=material_type, massdensity=massdensity, atomic_composition=atomic_composition)

    def get_conf(self):
        """
        Get configuration in form of a dictionary
        """
        conf = {}
        conf.update(AbstractParticle.get_conf(self))
        conf["diameter"] = self.diameter_mean
        dvar = self._diameter_variation.get_conf()
        conf["diameter_variation"] = dvar["mode"]
        conf["diameter_spread"] = dvar["spread"]
        conf["diameter_variation_n"] = dvar["n"]
        return conf
        
    def get_next(self):
        """
        Iterate the parameters of the Particle instance and return them as a dictionary
        """
        O = AbstractParticle.get_next(self)
        O["diameter"] = self._get_next_diameter()
        return O

    def set_diameter_variation(self, diameter_variation, diameter_spread, diameter_variation_n):
        r"""
        Set the variation scheme of the particle diameter
        
        Args:
          :diameter_variation (str): Variation of the particle diameter

            *Choose one of the following options:*

            ====================== ============================================================================================
            ``diameter_variation`` Type of variation
            ====================== ============================================================================================
            ``None``               No diameter variation
            ``'normal'``           Normal (*Gaussian*) variation
            ``'uniform'``          Uniformly distributed diameters within spread limits
            ``'range'``            Equidistant sequence of ``diameter_variation_n`` diameter samples within ``diameter_spread``
            ====================== ============================================================================================

          :diameter_spread (float): Statistical spread

          :diameter_variation_n (int): Number of particle-diameter samples within the specified range

            .. note:: The argument ``diameter_variation_n`` takes effect only if ``diameter_variation='range'``
        """
        self._diameter_variation = Variation(diameter_variation, diameter_spread, diameter_variation_n)       

    def _get_next_diameter(self):
        d = self._diameter_variation.get(self.diameter_mean)
        # Non-random diameter
        if self._diameter_variation._mode in [None,"range"]:
            if d <= 0:
                log_and_raise_error(logger,"Sample diameter smaller-equals zero. Change your configuration.")
            else:
                return d
        # Random diameter
        else:
            if d <= 0.:
                log_warning(logger, "Sample diameter smaller-equals zero. Try again.")
                return self._get_next_diameter()
            else:
                return d

    def set_material(self, material_type, massdensity, atomic_composition):
        """
        Initialise and set the Material class instance of the particle

        Args:
          :material_type (str): See :class:`condor.utils.material.Material`

          :massdensity (float): See :class:`condor.utils.material.Material`

          :atomic_composition (dict): See :class:`condor.utils.material.Material`
        """
        self.material = Material(material_type=material_type, massdensity=massdensity, atomic_composition=atomic_composition)


