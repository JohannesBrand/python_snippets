# a spectrogram data plot with tabs for the PX4 flight review tool

class DataPlotTabs(DataPlot):
    """
    A spectrogram plot.
    This does not do downsampling.
    """

    def __init__(self, data, config, data_name, x_axis_label=None,
                 y_axis_label=None, title=None, plot_height='small',
                 tabs_height='normal', x_range=None, y_range=None,
                 changed_params=None, topic_instance=0):

        self._had_error = False
        self._previous_success = False
        self._param_change_label = None
        self._title = title
        self._x_axis_label = x_axis_label
        self._y_axis_lable = y_axis_label

        self._data = data
        self._config = config
        self._data_name = data_name
        self._cur_dataset = None
        self._plots = []
        self._tabs = None
        self._changed_params = changed_params

        try:
            if y_range is not None:
                self._p.y_range = Range1d(y_range.start, y_range.end)
            if x_range is not None:
                # we need a copy, otherwise x-axis zooming will be synchronized
                # between all plots
                self._p.x_range = Range1d(x_range.start, x_range.end)

            self._cur_dataset = [elem for elem in data
                                 if elem.name == data_name and elem.multi_id == topic_instance][0]

        except (KeyError, IndexError, ValueError) as error:
            print(type(error), "(" + self._data_name + "):", error)
            self._had_error = True

        self._plot_width = self._config['plot_width']
        self._plot_height = self._config['plot_height'][plot_height]
        self._tabs_height = self._config['plot_height'][tabs_height]

    @property
    def title(self):
        """ return the bokeh title """
        return self._title

    @property
    def bokeh_plot(self):
        """ return the bokeh plot """
        return self._tabs

    def finalize(self):
        """ Call this after all plots are done. Returns the bokeh plot, or None
        on error """
        if self._had_error and not self._previous_success:
            return None

        if self._changed_params is not None:
            self._param_change_label = \
                plot_parameter_changes(self._plots[0], self._plot_height,
                                       self._changed_params)

        self._setup_plot()
        return self._tabs

    def _setup_plot(self):
        # offset = int(((1024/2.0)/250.0)*1e6)
        t_range = Range1d(start=self._cur_dataset.data['timestamp'][0],  # +offset,
                          end=self._cur_dataset.data['timestamp'][-1], bounds=None)
        for p in self._plots:
            p.toolbar.logo = None

            p.plot_width = self._plot_width
            p.plot_height = self._plot_height

            # -> other attributes are set via theme.yaml

            # disable x grid lines
            p.xgrid.grid_line_color = None

            p.toolbar.logo = None  # hide the bokeh logo (we give credit at the
            # bottom of the page)

            # p.lod_threshold=None # turn off level-of-detail

            # p.xaxis[0].ticker = BasicTicker(desired_num_ticks = 13)

            # axis labels: format time
            p.xaxis[0].formatter = FuncTickFormatter(code='''
                                //func arguments: ticks, x_range, t_range
                                // assume us ticks
                                ms = Math.round(tick * 1000 + t_range.start / 1000)
                                sec = Math.floor(ms / 1000)
                                minutes = Math.floor(sec / 60)
                                hours = Math.floor(minutes / 60)
                                ms = ms % 1000
                                sec = sec % 60
                                minutes = minutes % 60

                                function pad(num, size) {
                                    var s = num+"";
                                    while (s.length < size) s = "0" + s;
                                    return s;
                                }

                                if (hours > 0) {
                                    var ret_val = hours + ":" + pad(minutes, 2) + ":" + pad(sec,2)
                                } else {
                                    var ret_val = minutes + ":" + pad(sec,2);
                                }
                                if (x_range.end - x_range.start < 4) {
                                    ret_val = ret_val + "." + pad(ms, 3);
                                }
                                return ret_val;
                            ''', args={'x_range': p.x_range, 't_range': t_range})

            # make it possible to hide graphs by clicking on the label
            # p.legend.click_policy = "hide"

    def add_spec_graph(self, field_names, legends, use_downsample=True, mark_nan=False):
        """ add a spectrogram plot to the graph

        field_names can be a list of fields from the data set, or a list of
        functions with the data set as argument and returning a tuple of
        (field_name, data)
        :param mark_nan: if True, add an indicator to the plot when one of the graphs is NaN
        """

        if self._had_error: return
        try:
            data_set = {}
            data_set['timestamp'] = self._cur_dataset.data['timestamp']
            dt = ((data_set['timestamp'][-1] - data_set['timestamp'][0]) * 1.0e-6) / len(data_set['timestamp'])
            fs = int(1.0 / dt)

            field_names_expanded = self._expand_field_names(field_names, data_set)

            psd = dict()
            for key in field_names_expanded:
                f, t, psd[key] = signal.spectrogram(data_set[key],
                                                    fs=fs, window='hann', nperseg=256, noverlap=128, scaling='density')

            '''
            if use_downsample:
                # we directly pass the data_set, downsample and then create the
                # ColumnDataSource object, which is much faster than
                # first creating ColumnDataSource, and then downsample
                downsample = DynamicDownsample(p, data_set, 'timestamp')
                data_source = downsample.data_source
            else:
                data_source = ColumnDataSource(data=data_set)
            '''

            color_mapper = LinearColorMapper(palette=viridis(256), low=-80, high=0)

            tabs = []
            for field_name, legend in zip(field_names_expanded, legends):
                im = [10 * np.log10(psd[field_name])]
                self._plots.append(figure(title=self._title,
                                          plot_width=self._plot_width, plot_height=self._plot_height,
                                          x_range=(t[0], t[-1]), y_range=(f[0], f[-1]),
                                          x_axis_label=self._x_axis_label,
                                          y_axis_label=self._y_axis_lable, toolbar_location='above',
                                          tools=TOOLS, active_scroll=ACTIVE_SCROLL_TOOLS))
                self._plots[-1].image(image=im, x=t[0], y=f[0],
                                      dw=t[-1], dh=f[-1], color_mapper=color_mapper)
                color_bar = ColorBar(color_mapper=color_mapper,
                                     major_label_text_font_size="5pt",
                                     ticker=BasicTicker(desired_num_ticks=8),
                                     formatter=PrintfTickFormatter(format="%f"),
                                     label_standoff=6, border_line_color=None, location=(0, 0))
                self._plots[-1].add_layout(color_bar, 'right')
                tabs.append(Panel(child=self._plots[-1], title=legend))

            self._tabs = Tabs(tabs=tabs, width=self._plot_width,
                              height=self._tabs_height)

        except (KeyError, IndexError, ValueError) as error:
            print(type(error), "(" + self._data_name + "):", error)
            self._had_error = True
