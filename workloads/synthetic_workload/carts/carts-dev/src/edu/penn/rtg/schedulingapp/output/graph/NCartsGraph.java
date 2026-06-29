package edu.penn.rtg.schedulingapp.output.graph;


import javax.swing.JFrame;

import ptolemy.plot.plotml.PlotMLFrame;
import edu.penn.rtg.schedulingapp.basic.ResModel;
import edu.penn.rtg.schedulingapp.basic.Workload;
import edu.penn.rtg.schedulingapp.util.Debug;
/**
 * CartGraph use ptolemy plot library 
 * it draw graphical frame of sbf/dbf graph
 */

public class NCartsGraph {
	PlotMLFrame frame;
	NCartsPlot p;
	int endx=0;
	int startx=0;

	/**
	 * NCartGraph Constructor with plot class of Ptolemy project
	 * 
	 * @param plot ptolemy.plot.Plot
	 */

	public void init(String s,int n,boolean RBF)
	{
		p = new NCartsPlot();
		frame = new PlotMLFrame(s, p);
		frame.setLocation(0+n*25, 0+n*25);
		frame.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE);
		p.setTitle(s);
		p.setSize(700, 500);
		p.read("Lines: on");
		p.read("XLabel: Time");
		p.read("YLabel: Resource");
	}
	public void initApp()
	{
		frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
	}
	public void setXLimitEDF(ResModel rm,Workload wl) throws Exception{
		// fix range
		int lcm=wl.computeLCM();
		int sup=0,dem=0;
		int scope=0;
		int minDiff=-100;
		int repeat=0;
		for(int t=0;t<lcm;t++) {
			sup=rm.getSupply(t);
			dem=(int)wl.demand_EDF(t);
			if(dem==0) continue;
			if(minDiff==-100){
				minDiff=sup-dem;
				scope=t*2;
			}
			else if(sup-dem<=minDiff) {
				if(sup-dem==minDiff){
					if(repeat>5) {
						break;
					}
					repeat++;
				} else {
					repeat=0;
					minDiff=sup-dem;
				}
				scope=t*2;
			}
			//Debug.prn(t+","+minDiff);
		}
		//Debug.prn(scope);
		if(scope>lcm)
		{
			scope=lcm;
		}
		p.endAll(scope, rm.getSupply((scope)+1));
	}
	public void setRange(Workload wl)
	{
		int lcm=wl.computeLCM();
		if(lcm>60000)
			lcm=60000;
		endx=lcm;
	}
	public void setRange(int start, int end)
	{
		startx=start;
		endx=end;
	}
	public void drawSBF(ResModel rm) throws Exception
	{
		p.startSBF(); 
		int sup=0;
		for(int t=0;t<=endx;t++)
		{
			sup=rm.getSupply(t);
			//Debug.prn(t+","+sup);
			p.addSup(t, sup);
		}
	}
	public void drawDBF(Workload wl)
	{
		p.startDBF(); 
		int dem=0,old_dem=0;
		for(int t=0;t<endx;t++)
		{
			dem=(int)wl.demand_EDF(t);
			if(dem!=old_dem){
				//Debug.prn(t+","+dem);
				p.addDem(t, dem);
				old_dem=dem;
			}
		}
		p.addDem(endx, dem);

	}
	public void drawDBF_MPR(Workload wl,int m,int k) {
		p.startDBF(); 
		int dem=0,old_dem=0;
		for(int t=0;t<endx;t++)
		{
			dem=wl.computeDEM(m, k, t);
			dem=Math.max(0, dem);
			if(dem!=old_dem){
				//Debug.prn(t+","+dem);
				p.addDem(t, dem);
				old_dem=dem;
			}
		}
		p.addDem(endx, dem);
		p.endX1x2(startx,endx);
	}
	/**
	 * Show graph frame
	 * 
	 */
	public void show() {
		frame.setVisible(true);
	}
}
