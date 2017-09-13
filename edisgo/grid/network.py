import edisgo
from edisgo.tools import config
from edisgo.data.import_data import import_from_ding0#, import_generators
from edisgo.flex_opt.costs import grid_expansion_costs

from os import path
import pandas as pd
from edisgo.tools import pypsa_io
from math import sqrt


class Network:
    """Defines the eDisGo Network

    Used as container for all data related to a single
    :class:`~.grid.grids.MVGrid`.
    Provides the top-level API for invocation of data import, analysis of
    hosting capacity, grid reinforce and flexibility measures.

    Examples
    --------
    Assuming you the Ding0 `ding0_data.pkl` in CWD

    Create eDisGo Network object by loading Ding0 file

    >>> from edisgo.grid.network import Network
    >>> network = Network.import_from_ding0('ding0_data.pkl'))

    Analyze hosting capacity for MV grid level

    >>> network.analyze(mode='mv')

    Print LV station secondary side voltage levels returned by PFA

    >>> lv_stations = network.mv_grid.graph.nodes_by_attribute('lv_station')
    >>> print(network.results.v_res(lv_stations, 'lv'))

    Attributes
    ----------
    _metadata : :obj:`dict`
        Metadata of Network such as ?
    """

    def __init__(self, **kwargs):
        if 'pypsa' not in kwargs.keys():
            self._id = kwargs.get('id', None)
            self._metadata = kwargs.get('metadata', None)
            self._data_sources = kwargs.get('data_sources', {})
            self._scenario = kwargs.get('scenario', None)
            self._mv_grid = kwargs.get('mv_grid', None)
            self._pypsa = None
            self.results = Results()
        else:
            self._pypsa = kwargs.get('pypsa', None)

        self._config = self._load_config()
        self._equipment_data = self._load_equipment_data()

    @staticmethod
    def _load_config():
        """Load config files

        Returns
        -------
        config object
        """

        config.load_config('config_db_tables.cfg')
        config.load_config('config_data.cfg')
        config.load_config('config_flexopt.cfg')
        config.load_config('config_misc.cfg')
        config.load_config('config_scenario.cfg')

        return config.cfg._sections

    def _load_equipment_data(self):
        """Load equipment data for transformers, cables etc.

        Returns
        -------
        :obj:`dict` of :pandas:`pandas.DataFrame<dataframe>`
        """

        package_path =  edisgo.__path__[0]
        equipment_dir = self._config['system_dirs']['equipment_dir']

        data = {}

        equipment_mv_parameters_trafos = self._config['equipment']['equipment_mv_parameters_trafos']
        data['MV_trafos'] = pd.read_csv(path.join(package_path, equipment_dir,
                                                  equipment_mv_parameters_trafos),
                                        comment='#',
                                        index_col='name',
                                        delimiter=',',
                                        decimal='.'
                                        )


        equipment_mv_parameters_lines = self._config['equipment']['equipment_mv_parameters_lines']
        data['MV_lines'] = pd.read_csv(path.join(package_path, equipment_dir,
                                                 equipment_mv_parameters_lines),
                                       comment='#',
                                       index_col='name',
                                       delimiter=',',
                                       decimal='.'
                                       )

        equipment_mv_parameters_cables = self._config['equipment']['equipment_mv_parameters_cables']
        data['MV_cables'] = pd.read_csv(path.join(package_path, equipment_dir,
                                                  equipment_mv_parameters_cables),
                                        comment='#',
                                        index_col='name',
                                        delimiter=',',
                                        decimal='.'
                                        )

        equipment_lv_parameters_cables = self._config['equipment']['equipment_lv_parameters_cables']
        data['LV_cables'] = pd.read_csv(path.join(package_path, equipment_dir,
                                                  equipment_lv_parameters_cables),
                                        comment='#',
                                        index_col='name',
                                        delimiter=',',
                                        decimal='.'
                                        )

        equipment_lv_parameters_trafos = self._config['equipment']['equipment_lv_parameters_trafos']
        data['LV_trafos'] = pd.read_csv(path.join(package_path, equipment_dir,
                                                  equipment_lv_parameters_trafos),
                                        comment='#',
                                        index_col='name',
                                        delimiter=',',
                                        decimal='.'
                                        )

        return data

    @classmethod
    def import_from_ding0(cls, file, **kwargs):
        """Import grid data from DINGO file

        For details see
        :func:`edisgo.data.import_data.import_from_ding0`
        """

        # create the network instance
        network = cls(**kwargs)

        # call the importer
        import_from_ding0(file, network)

        return network

    def import_generators(self):
        """Imports generators

        TBD

        """
        raise NotImplementedError

    def analyze(self, mode=None):
        """Analyzes the grid by power flow analysis

        Analyze the grid for violations of hosting capacity. Means, perform a
        power flow analysis and obtain voltages at nodes (load, generator,
        stations/transformers and branch tees) and active/reactive power at
        lines.

        The power flow analysis can be performed for both grid levels MV and LV
        and for both of them individually. Use `mode` to choose (defaults to
        MV + LV).

        A static `non-linear power flow analysis is performed using PyPSA
        <https://www.pypsa.org/doc/power_flow.html#full-non-linear-power-flow>`_.
        The high-voltage to medium-voltage transformer are not included in the
        analysis. The slack bus is defined at secondary side of these
        transformers assuming an ideal tap changer. Hence, potential overloading
        of the transformers is not studied here.

        Parameters
        ----------
        mode: str
            Allows to toggle between power flow analysis (PFA) on the whole grid
            topology (MV + LV), only MV or only LV. Therefore, either specify
            `mode='mv'` for PFA of the MV grid topology or `mode='lv'`
            for PFA of the LV grid topology.
            Defaults to None which equals power flow analysis for MV + LV.

        Notes
        -----
        The current implementation always translates the grid topology
        representation to the PyPSA format and stores it to :attr:`self._pypsa`.

        TODO: extend doctring by

        * How power plants are modeled, if possible use a link
        * Where to find and adjust power flow analysis defining parameters

        See Also
        --------
        :func:~.tools.pypsa_io.to_pypsa
            Translator to PyPSA data format

        """
        self.pypsa = pypsa_io.to_pypsa(self, mode)

        # run power flow analysis
        self.pypsa.pf(self.pypsa.snapshots)

        pypsa_io.process_pfa_results(self, self.pypsa)


    def reinforce(self):
        """Reinforces the grid

        TBD

        """
        raise NotImplementedError

    @property
    def id(self):
        """Returns id of network"""
        return self._id

    @property
    def config(self):
        """Returns config object"""
        return self._config

    @property
    def equipment_data(self):
        """Returns equipment data object

        Electrical equipment such as lines and transformers
        :obj:`dict` of :pandas:`pandas.DataFrame<dataframe>`
        """
        return self._equipment_data

    @property
    def mv_grid(self):
        """:class:`~.grid.grids.MVGrid` : Medium voltage (MV) grid

        Retrieve the instance of the loaded MV grid
        """
        return self._mv_grid

    @mv_grid.setter
    def mv_grid(self, mv_grid):
        self._mv_grid = mv_grid

    @property
    def data_sources(self):
        """:obj:`dict` of :obj:`str` : Data Sources

        """
        return self._data_sources

    def set_data_source(self, key, data_source):
        """Set data source for key (e.g. 'grid')
        """
        self._data_sources[key] = data_source

    @property
    def pypsa(self):
        """
        PyPSA grid representation

        A grid topology representation based on
        :pandas:`pandas.DataFrame<dataframe>`. The overall container object of
        this data model the
        `PyPSA network <https://www.pypsa.org/doc/components.html#network>`_
        is assigned to this attribute.
        This allows as well to overwrite data.

        Parameters
        ----------
        pypsa:
            The `PyPSA network <https://www.pypsa.org/doc/components.html#network>`_
            container

        Returns
        -------
        PyPSA grid representation
        """
        return self._pypsa

    @pypsa.setter
    def pypsa(self, pypsa):
        self._pypsa = pypsa

    @property
    def scenario(self):
        return self._scenario

    @scenario.setter
    def scenario(self, scenario):
        self._scenario = scenario

    def __repr__(self):
        return 'Network ' + self._id


class Scenario:
    """Defines an eDisGo scenario

    It contains parameters and links to further data that is used for
    calculations within eDisGo.

    Attributes
    ----------
    _name : :obj:`str`
        Scenario name (e.g. "feedin case weather 2011")
    _network : :class:~.grid.network.Network`
        Network which this scenario is associated with
    _timeseries : :obj:`list` of :class:`~.grid.grids.TimeSeries`
        Time series associated to a scenario
    _etrago_specs : :class:`~.grid.grids.ETraGoSpecs`
        Specifications which are to be fulfilled at transition point (HV-MV
        substation)
    _pfac_mv_gen : :obj:`float`
        Power factor for medium voltage generators
    _pfac_mv_load : :obj:`float`
        Power factor for medium voltage loads
    _pfac_lv_gen : :obj:`float`
        Power factor for low voltage generators
    _pfac_lv_load : :obj:`float`
        Power factor for low voltage loads
    """

    def __init__(self, **kwargs):
        self._name = kwargs.get('name', None)
        self._network = kwargs.get('network', None)
        self._timeseries = kwargs.get('timeseries', None)
        self._etrago_specs = kwargs.get('etrago_specs', None)
        self._pfac_mv_gen = kwargs.get('pfac_mv_gen', None)
        self._pfac_mv_load = kwargs.get('pfac_mv_load', None)
        self._pfac_lv_gen = kwargs.get('pfac_lv_gen', None)
        self._pfac_lv_load = kwargs.get('pfac_lv_load', None)

    @property
    def timeseries(self):
        return self._timeseries

    def __repr__(self):
        return 'Scenario ' + self._name


class TimeSeries:
    """Defines an eDisGo time series

    Contains time series for loads (sector-specific) and generators
    (technology-specific), e.g. tech. solar, sub-tech. rooftop.

    Attributes
    ----------
    _generation : :obj:`dict` of :obj:`dict` of :pandas:`pandas.Series<series>`
        Time series of active power of generators for technologies and
        sub-technologies, format:

        .. code-block:: python

            {tech_1: {
                sub-tech_1_1: timeseries_1_1,
                ...,
                sub-tech_1_n: timeseries_1_n},
                 ...,
            tech_m: {
                sub-tech_m_1: timeseries_m_1,
                ...,
                sub-tech_m_n: timeseries_m_n}
            }

    _load : :obj:`dict` of :pandas:`pandas.Series<series>`
        Time series of active power of (cumulative) loads,
        format:

        .. code-block:: python

            {
                sector_1:
                    timeseries_1,
                    ...,
                sector_n:
                    timeseries_n
            }

    See also
    --------
    edisgo.grid.components.Generator : Usage details of :meth:`_generation`
    edisgo.grid.components.Load : Usage details of :meth:`_load`
    """

    def __init__(self, **kwargs):
        self._generation = kwargs.get('generation', None)
        self._load = kwargs.get('load', None)

    @property
    def timeindex(self):
        # TODO: replace this dummy when time series are ready. Replace by the index of one of the DataFrames
        hours_of_the_year = 8760
        return pd.date_range('12/4/2011', periods=2, freq='H')


class ETraGoSpecs:
    """Defines an eTraGo object used in project open_eGo

    Contains specifications which are to be fulfilled at transition point
    (superiorHV-MV substation) for a specific scenario.

    Attributes
    ----------
    _active_power : :pandas:`pandas.Series<series>`
        Time series of active power at Transition Point
    _reactive_power : :pandas:`pandas.Series<series>`
        Time series of reactive power at Transition Point
    _battery_capacity: :obj:`float`
        Capacity of virtual battery at Transition Point
    _battery_active_power : :pandas:`pandas.Series<series>`
        Time series of active power the (virtual) battery (at Transition Point)
        is charged (negative) or discharged (positive) with
    _dispatch : :obj:`dict` of :obj:`dict` of :pandas:`pandas.Series<series>`
        Time series of actual dispatch and a time series of power generation
        potential (without curtailment) for technologies
        and sub-technologies, format::

            {
                tech_1: {
                    sub-tech_1_1:
                        timeseries_1_1,
                        ...,
                    sub-tech_1_n:
                    timeseries_1_n
                    },
                ...,
                tech_m: {
                    sub-tech_m_1:
                        timeseries_m_1,
                        ...,
                    sub-tech_m_n:
                        timeseries_m_n
                        }
                 }

        .. TODO: Is this really an active power value or a ratio (%) ?
    """

    def __init__(self, **kwargs):
        self._active_power = kwargs.get('active_power', None)
        self._reactive_power = kwargs.get('reactive_power', None)
        self._battery_capacity = kwargs.get('battery_capacity', None)
        self._battery_active_power = kwargs.get('battery_active_power', None)
        self._dispatch = kwargs.get('dispatch', None)


class Results:
    """
    Power flow analysis results management

    Includes raw power flow analysis results, history of measures to increase
    the grid's hosting capacity and information about changes of equipment.

    Attributes
    ----------
    measures: list
        A stack that details the history of measures to increase grid's hosting
        capacity. The last item refers to the latest measure. The key `original`
        refers to the state of the grid topology as it was initially imported.
    equipment_changes: :pandas:`pandas.DataFrame<dataframe>`
        Tracks changes in the equipment (replaced or added cable, batteries
        added, curtailment set to a generator, ...). This is indexed by the
        components (nodes or edges) and has following columns:

        equipment: detailing what was changed (line, battery, curtailment). For
        ease of referencing we take the component itself. For lines we take the
        line-dict, for batteries the battery-object itself and for curtailment
        either a dict providing the details of curtailment or a curtailment
        object if this makes more sense (has to be defined).

        change: {added | removed} - says if something was added or removed
    grid_expansion_costs: float
        Total costs of grid expansion measures in `equipment_changes`.
        ToDo: add unit
    """

    # TODO: maybe add setter to alter list of measures

    def __init__(self):
        self._measures = ['original']
        self._pfa_p = None
        self._pfa_q = None
        self._pfa_v_mag_pu = None
        self._equipment_changes = pd.DataFrame()

    @property
    def pfa_p(self):
        """
        Active power results from power flow analysis

        Holds power flow analysis results for active power for the last
        iteration step. Index of the DataFrame is a DatetimeIndex indicating
        the time period the power flow analysis was conducted for; columns
        of the DataFrame are the edges as well as stations of the grid
        topology.
        ToDo: add unit

        Parameters
        ----------
        pypsa: `pandas.DataFrame<dataframe>`
            Results time series of active power P from the
            `PyPSA network <https://www.pypsa.org/doc/components.html#network>`_

            Provide this if you want to set values. For retrieval of data do not
            pass an argument

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Active power results from power flow analysis
        """
        return self._pfa_p

    @pfa_p.setter
    def pfa_p(self, pypsa):
        self._pfa_p = pypsa

    @property
    def pfa_q(self):
        """
        Reactive power results from power flow analysis

        Holds power flow analysis results for reactive power for the last
        iteration step. Index of the DataFrame is a DatetimeIndex indicating
        the time period the power flow analysis was conducted for; columns
        of the DataFrame are the edges as well as stations of the grid
        topology.
        ToDo: add unit

        Parameters
        ----------
        pypsa: `pandas.DataFrame<dataframe>`
            Results time series of reactive power Q from the
            `PyPSA network <https://www.pypsa.org/doc/components.html#network>`_

            Provide this if you want to set values. For retrieval of data do not
            pass an argument

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Reactive power results from power flow analysis

        """
        return self._pfa_q

    @pfa_q.setter
    def pfa_q(self, pypsa):
        self._pfa_q = pypsa

    @property
    def pfa_v_mag_pu(self):
        """
        Voltage deviation at node in p.u.

        Holds power flow analysis results for relative voltage deviation for
        the last iteration step. Index of the DataFrame is a DatetimeIndex
        indicating the time period the power flow analysis was conducted for;
        columns of the DataFrame are the nodes as well as stations of the grid
        topology.

        Parameters
        ----------
        pypsa: `pandas.DataFrame<dataframe>`
            Results time series of voltage deviation from the
            `PyPSA network <https://www.pypsa.org/doc/components.html#network>`_

            Provide this if you want to set values. For retrieval of data do not
            pass an argument

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Voltage level nodes of grid

        """
        return self._pfa_v_mag_pu

    @pfa_v_mag_pu.setter
    def pfa_v_mag_pu(self, pypsa):
        if self._pfa_v_mag_pu is None:
            self._pfa_v_mag_pu = pypsa
        else:
            self._pfa_v_mag_pu = pd.concat([self._pfa_v_mag_pu, pypsa], axis=1)



    def s_res(self, lines=None):
        """
        Get resulting apparent power at line(s)

        The apparent power at a line determines from the maximum values of
        active power P and reactive power Q.

        .. math::

            S = \sqrt(max(p0, p1)^2 + max(q0, q1)^2)

        Parameters
        ----------
        lines : :class:`~.grid.components.Load` or list of :class:`~.grid.components.Load`

            Line objects of grid topology. If not provided (respectively None)
            defaults to return `s_res` of all lines in the grid.

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Apparent power for `lines`

        """


        if lines is not None:
            labels_included = []
            labels_not_included = []
            labels = [repr(l) for l in lines]
            for label in labels:
                if label in list(self.pfa_p.columns) and label in list(self.pfa_q.columns):
                    labels_included.append(label)
                else:
                    labels_not_included.append(label)
                    print(
                        "Apparent power for {lines} are not returned from PFA".format(
                            lines=labels_not_included))
        else:
            labels_included = self.pfa_p.columns

        s_res = ((self.pfa_p[labels_included] ** 2 + self.pfa_q[
            labels_included] ** 2) * 1e3).applymap(sqrt)

        return s_res

    def v_res(self, nodes=None, level=None):
        """
        Get resulting voltage level at node

        Parameters
        ----------
        nodes :  {:class:`~.grid.components.Load`, :class:`~.grid.components.Generator`, ...} or :obj:`list` of
            grid topology component or `list` grid topology components
            If not provided defaults to column names available in grid level
            `level`
        level : str
            Either 'mv' or 'lv' or None (default). Depending which grid level results you are
            interested in. It is required to provide this argument in order
            to distinguish voltage levels at primary and secondary side of the
            transformer/LV station.
            If not provided (respectively None) defaults to `['mv', 'lv'].

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            Resulting voltage levels obtained from power flow analysis

        Notes
        -----
        Limitation:  When power flow analysis is performed for MV only
        (with aggregated LV loads and generators) this methods only returns
        voltage at secondary side busbar and not at load/generator.

        """
        if level is None:
            level = ['mv', 'lv']

        if nodes is None:
            labels = list(self.pfa_v_mag_pu[level])
        else:
            labels = [repr(_) for _ in nodes]

        not_included = [_ for _ in labels
                        if _ not in list(self.pfa_v_mag_pu[level].columns)]

        labels_included = [_ for _ in labels if _ not in not_included]

        if not_included:
            print("Voltage levels for {nodes} are not returned from PFA".format(
                nodes=not_included))


        return self.pfa_v_mag_pu[level][labels_included]