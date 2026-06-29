package edu.penn.rtg.schedulingapp.output.graph;



import javax.swing.JFrame;

import ptolemy.plot.plotml.PlotMLFrame;
import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.output.graph.CartsPlot;
/**
 * CartGraph use ptolemy plot library 
 * it draw graphical frame of sbf/dbf graph
 */

public class CartsGraph {
	PlotMLFrame frame;
	CartsPlot p;
	int xLimit=0;

	/**
	 * CartGraph Constructor with plot class of Ptolemy project
	 * 
	 * @param plot ptolemy.plot.Plot
	 */

	public void init(String s,int n,boolean RBF)
	{
		p = new CartsPlot(RBF);
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
	
	public void setLimit(int x){
		xLimit=x;
		//lastx=(int) (x*1.05+1);
	}
	public void drawSBF(ResourceModel rm)
	{
		p.startSBF(); 
		double exec=rm.getBandwidth()*rm.getPeriod();
		p.addStarvation(rm.getPeriod()+rm.getDeadline()-2*exec);
		//System.out.println(rm.getPeriod()+rm.getDeadline()-2*exec);
		p.drawUntil(exec, rm.getPeriod()-exec, xLimit);
		//System.out.println(exec);
	}
	public void drawSBF_DPRM(ResourceModel rm)
	{
		p.startSBF(); 
		int period1=(int) rm.getPeriod();
		int exec1=(int) rm.getBandwidth();
		p.drawDPRM(period1,exec1,rm.period2,rm.exec2, xLimit);
	}
	public void drawSBF_Arinc(ResourceModel rm)
	{
		p.startSBF(); 
		double exec=rm.getBandwidth()*rm.getPeriod();
		p.addStarvation(rm.getPeriod()-exec);
		p.drawUntil(exec, rm.getPeriod()-exec, xLimit);
	}
	public void drawDBF(SchedulingComponent c)
	{
		p.startDBF();
		double d=0;
		double old_d=0;
		for(int i=1;i<=xLimit;i++){
			d=c.computeDBF(i,  (int) c.getMaxPeriod());
			if(d!=old_d){
				//System.out.println(i+","+d);
				p.addDem(i,d);
				old_d=d;
			}
		}
		p.addDem(xLimit, d);
	}
	public void findTight(SchedulingComponent c,ResourceModel rm)
	{
		double d=0,s=0;
		double min=100000;
		double minx=0,miny=0;
		for(int i=1;i<=xLimit;i++){
			d=c.computeDBF(i,  (int) c.getMaxPeriod());
			s=rm.computeSBF(i);
			if(d!=0)
			{
				if(s-d<0.0001)
				{
					minx=getRange(i);
					miny=getRange((int)d);
					break;
				}
				if(s-d<min)
				{
					min=s-d;
					minx=getRange(i);
					miny=getRange((int)d);
				}
			}	
		}
		if(minx>xLimit)
		{
			minx=xLimit;
			miny=rm.computeSBF(minx);
		}
		//System.out.println("min:"+min+","+minx+","+miny);
		p.endAll(minx,miny);
	}
	public void findTightDPRM(SchedulingComponent c,ResourceModel rm)
	{
		double d=0,s=0;
		double min=100000;
		double minx=0,miny=0;
		for(int i=1;i<=xLimit;i++){
			d=c.computeDBF(i,  (int) c.getMaxPeriod());
			s=rm.computeSBF_DPRM(i);
			if(d!=0)
			{
				if(s-d<0.0001)
				{
					minx=getRange(i);
					miny=getRange((int)d);
					break;
				}
				if(s-d<min)
				{
					min=s-d;
					minx=getRange(i);
					miny=getRange((int)d);
				}
			}	
		}
		if(minx>xLimit)
		{
			minx=xLimit;
			miny=rm.computeSBF_DPRM((int) minx);
		}
		//System.out.println("min:"+min+","+minx+","+miny);
		p.endAll(minx,miny);
	}
	private int getRange(int v)
	{
		if(v<10)
		{
			return (int)(v*1.7)+3;
		}
		else if(v<100)
		{
			return (int)(v*1.5)+5;
		}
		else if( v< 1000)
		{
			return (int)(v*1.05)+10;
		}
		else
		{
			return (int)(v*1.05)+100;
		}
	}
	public void drawRBF(SchedulingComponent c,int ind)
	{
		p.startDBF();
		double d=0;
		double old_d=0;
		for(int i=0;i<=xLimit;i++){
			d=c.computeRBF(i+1, ind, (int) c.getMaxPeriod());
			if(d!=old_d){
				//System.out.println(i+","+d);
				p.addDem(i,d);
				old_d=d;
			}
		}
		p.addDem(xLimit, d);
		p.endAll();
	}
	public void drawSIRAP(SchedulingComponent c,int ind)
	{
		p.startDBF();
		double d=0;
		double old_d=0;
		for(int i=0;i<=xLimit;i++){
			d=c.computeRBF_SIRAP(i+1, ind, (int) c.getMaxPeriod());
			if(d!=old_d){
				//System.out.println(i+","+d);
				p.addDem(i,d);
				old_d=d;
			}
		}
		p.addDem(xLimit, d);
		p.endAll();
	}
	public void circle(double x,double y){
		p.circle(x, y);
	}
	/**
	 * Show graph frame
	 * 
	 */
	public void show() {
		frame.setVisible(true);
	}
}
