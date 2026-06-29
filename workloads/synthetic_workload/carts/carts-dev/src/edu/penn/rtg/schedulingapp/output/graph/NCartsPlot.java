package edu.penn.rtg.schedulingapp.output.graph;

import java.awt.Color;

import ptolemy.plot.Plot;
/**
 * It extends ptolemy.plot.Plot for sbf/dbf graph
 */

@SuppressWarnings("serial")
public class NCartsPlot extends Plot {
	double maxX = 0;
	double maxY = 0;
	double lasty=0;
	double lastx=0;
	static protected Color[] _colors = {
		new Color(0x00aaaa), // cyan-ish
		new Color(0xff0000), // red
		new Color(0x0000ff), // blue
		new Color(0x000000), // black
		new Color(0xffa500), // orange
		new Color(0x53868b), // cadetblue4
		new Color(0xff7f50), // coral
		new Color(0x45ab1f), // dark green-ish
		new Color(0x90422d), // sienna-ish
		new Color(0xa0a0a0), // grey-ish
		new Color(0x14ff14), // green-ish
		};

	/**
	 * Start to draw Supply Bound Function 
	 * 
	 */
	public NCartsPlot()
	{
		setColors(_colors);
				
	}
	public void startSBF() {
		read("Dataset: Supply");
		read("Color:red");
		read("0,0");
		lasty=0;
	}
	/**
	 * Start to draw Demand Bound Function 
	 * 
	 */

	public void startDBF() {
		read("Dataset: Demand");
		read("Color: blue");
		read("0,0");
		lasty=0;
	}
	
	public void addDem(double x,double y){
		add(x,lasty);
		add(x,y);
		lasty=y;
	}
	public void addSup(double x,double y){
		add(x,y);
	}

	/**
	 * Draw from current location to specific point
	 * 
	 * @param x x-axis value of point
	 * @param y y-axis value of point
	 */

	public void add(double x, double y) {
		//System.out.println(x + "," + y);
		read(x + "," + y);
		if (x > maxX)
			maxX = x;
		if (y > maxY)
			maxY = y;
	}
	public void circle(double x,double y){
		read("Dataset: sbf >= rbf");
		read("Impulses: on");
		read("Marks: dots");
		read(x + "," + y);
	}

	/**
	 * End to draw graph
	 * 
	 */

	public void endAll() {
		read("XRange: 0," + maxX);
		read("YRange: 0," + maxY);
	}
	public void endAll(double x,double y)
	{
		read("XRange: 0," + x);
		read("YRange: 0," + y);
	}
	public void endX1x2(double x1,double x2)
	{
		read("XRange:"+x1+"," + x2);
		read("YRange: 0," + maxY+1);
	}
	
}
